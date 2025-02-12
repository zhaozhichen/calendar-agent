// API configuration
const API_BASE_URL = window.location.origin;

// Calendar instance
let calendar;

// Initialize the application
document.addEventListener('DOMContentLoaded', async function() {
    // Initialize FullCalendar
    const calendarEl = document.getElementById('calendar');
    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        slotMinTime: '09:00:00',
        slotMaxTime: '17:00:00',
        allDaySlot: false,
        height: 'auto',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay'
        },
        views: {
            timeGridWeek: {
                slotDuration: '00:30:00',
                slotLabelInterval: '01:00',
                slotEventOverlap: true,
                nowIndicator: true,
                dayHeaderFormat: { weekday: 'short', month: 'numeric', day: 'numeric', omitCommas: true }
            },
            dayGridMonth: {
                dayMaxEvents: 3,
                showMore: true
            }
        },
        eventContent: function(arg) {
            return {
                html: `
                    <div class="fc-event-main-content">
                        <div class="fc-event-title">${arg.event.title}</div>
                        <div class="fc-event-time" style="font-size: 0.8em;">
                            ${arg.timeText}
                            <span class="badge bg-secondary ms-1">Priority: ${arg.event.extendedProps.priority || 'N/A'}</span>
                        </div>
                    </div>
                `
            };
        },
        eventClick: function(info) {
            showEventDetails(info.event);
        },
        eventDidMount: function(info) {
            // Add tooltip with event details
            info.el.title = `${info.event.title}
Time: ${formatDateTime(info.event.start)} - ${formatDateTime(info.event.end)}
Priority: ${info.event.extendedProps.priority || 'N/A'}
Organizer: ${info.event.extendedProps.organizer}
Attendees: ${info.event.extendedProps.attendees.join(', ')}`;
        }
    });
    calendar.render();

    // Load agents
    await loadAgents();

    // Set up meeting modal defaults
    const scheduleMeetingModal = document.getElementById('scheduleMeetingModal');
    scheduleMeetingModal.addEventListener('show.bs.modal', function () {
        // Set default dates
        const today = new Date();
        const nextWeek = new Date(today);
        nextWeek.setDate(today.getDate() + 7);

        // Format dates as YYYY-MM-DD for input fields
        const startDateInput = document.getElementById('meetingStartDate');
        const endDateInput = document.getElementById('meetingEndDate');
        
        // Set minimum date to today to prevent selecting past dates
        const todayStr = today.toISOString().split('T')[0];
        startDateInput.min = todayStr;
        endDateInput.min = todayStr;
        
        startDateInput.value = todayStr;
        endDateInput.value = nextWeek.toISOString().split('T')[0];
    });
});

// Load agents into dropdowns
async function loadAgents() {
    try {
        const response = await fetch(`${API_BASE_URL}/agents`);
        const data = await response.json();
        
        const agentSelect = document.getElementById('agentSelect');
        const organizerSelect = document.getElementById('meetingOrganizer');
        const attendeesContainer = document.getElementById('meetingAttendees');
        
        // Clear existing options except the first one for dropdowns
        [agentSelect, organizerSelect].forEach(select => {
            while (select.options.length > 1) {
                select.remove(1);
            }
        });
        
        // Clear attendees container
        attendeesContainer.innerHTML = '';
        
        // Sort agents alphabetically
        const sortedAgents = [...data.agents].sort((a, b) => a.localeCompare(b));
        
        // Add sorted agents to dropdowns
        sortedAgents.forEach(email => {
            [agentSelect, organizerSelect].forEach(select => {
                const option = new Option(email, email);
                select.add(option);
            });
        });

        // Create select all checkbox
        const selectAllDiv = document.createElement('div');
        selectAllDiv.className = 'form-check mb-2';
        selectAllDiv.innerHTML = `
            <input class="form-check-input" type="checkbox" id="selectAllAttendees">
            <label class="form-check-label" for="selectAllAttendees">
                Select All
            </label>
        `;
        attendeesContainer.appendChild(selectAllDiv);

        // Add individual attendee checkboxes
        sortedAgents.forEach(email => {
            const div = document.createElement('div');
            div.className = 'form-check';
            div.innerHTML = `
                <input class="form-check-input attendee-checkbox" type="checkbox" value="${email}" id="attendee-${email}">
                <label class="form-check-label" for="attendee-${email}">
                    ${email}
                </label>
            `;
            attendeesContainer.appendChild(div);
        });

        // Add event listeners
        const selectAllCheckbox = document.getElementById('selectAllAttendees');
        const attendeeCheckboxes = document.querySelectorAll('.attendee-checkbox');

        selectAllCheckbox.addEventListener('change', function() {
            attendeeCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
        });

        attendeeCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                selectAllCheckbox.checked = 
                    Array.from(attendeeCheckboxes).every(cb => cb.checked);
            });
        });

        // Add event listener for organizer selection to auto-check their checkbox
        organizerSelect.addEventListener('change', function() {
            const selectedOrganizer = this.value;
            if (selectedOrganizer) {
                const organizerCheckbox = document.getElementById(`attendee-${selectedOrganizer}`);
                if (organizerCheckbox) {
                    organizerCheckbox.checked = true;
                }
            }
        });

    } catch (error) {
        showError('Failed to load agents: ' + error.message);
    }
}

// Load calendar events for selected agent
async function onAgentSelect(email) {
    if (!email) return;
    
    try {
        showLoading();
        
        // Calculate date range (2 weeks)
        const start = new Date();
        start.setHours(0, 0, 0, 0);
        const end = new Date(start);
        end.setDate(end.getDate() + 14);
        
        const response = await fetch(
            `${API_BASE_URL}/agents/${email}/availability?` +
            `start_time=${start.toISOString()}&` +
            `end_time=${end.toISOString()}`
        );
        
        const data = await response.json();
        
        // Clear existing events
        calendar.removeAllEvents();
        
        // Add new events
        const events = data.events.map(event => ({
            id: event.id,
            title: event.title,
            start: event.start,
            end: event.end,
            description: event.description,
            attendees: event.attendees,
            organizer: event.organizer,
            className: `user-${event.organizer.split('@')[0]}`,
            extendedProps: {
                organizer: event.organizer,
                attendees: event.attendees,
                description: event.description,
                priority: event.priority
            }
        }));
        
        console.log('Events with priorities:', events.map(e => ({
            title: e.title,
            priority: e.extendedProps.priority
        })));
        
        calendar.addEventSource({ events });
        hideLoading();
    } catch (error) {
        hideLoading();
        showError('Failed to load calendar: ' + error.message);
    }
}

// Show event details in modal
function showEventDetails(event) {
    const modalBody = document.querySelector('#meetingDetailsModal .modal-body');
    modalBody.innerHTML = `
        <p><strong>Time:</strong> <span id="detailTime">${formatDateTime(event.start)} - ${formatDateTime(event.end)}</span></p>
        <p><strong>Priority:</strong> <span class="badge bg-secondary">${event.extendedProps.priority || 'N/A'}</span></p>
        <p><strong>Organizer:</strong> <span id="detailOrganizer">${event.extendedProps.organizer}</span></p>
        <p><strong>Attendees:</strong> <span id="detailAttendees">${event.extendedProps.attendees.join(', ')}</span></p>
        <p><strong>Description:</strong> <span id="detailDescription">${event.extendedProps.description || 'No description'}</span></p>
    `;
    
    // Add delete button to modal footer
    const modalFooter = document.querySelector('#meetingDetailsModal .modal-footer');
    if (!modalFooter) {
        const footer = document.createElement('div');
        footer.className = 'modal-footer';
        document.querySelector('#meetingDetailsModal .modal-content').appendChild(footer);
    }
    
    const modalFooterContent = document.querySelector('#meetingDetailsModal .modal-footer');
    modalFooterContent.innerHTML = `
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
        <button type="button" class="btn btn-danger" onclick="deleteEvent('${event.id}', '${event.title}')">Delete Event</button>
    `;
    
    document.getElementById('detailTitle').textContent = event.title;
    const modal = new bootstrap.Modal(document.getElementById('meetingDetailsModal'));
    modal.show();
}

// Add delete event function
async function deleteEvent(eventId, eventTitle) {
    if (!confirm(`Are you sure you want to delete the event "${eventTitle}"?`)) {
        return;
    }
    
    try {
        showLoading();
        const selectedAgent = document.getElementById('agentSelect').value;
        if (!selectedAgent) {
            throw new Error('No agent selected');
        }
        
        const response = await fetch(`${API_BASE_URL}/agents/${selectedAgent}/events/${eventId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Failed to delete event');
        }
        
        hideLoading();
        showSuccess(`Successfully deleted event "${eventTitle}"`);
        
        // Close the modal
        bootstrap.Modal.getInstance(document.getElementById('meetingDetailsModal')).hide();
        
        // Refresh the calendar
        await onAgentSelect(selectedAgent);
        
    } catch (error) {
        hideLoading();
        showError('Failed to delete event: ' + error.message);
    }
}

// Format date and time
function formatDateTime(date) {
    const dt = new Date(date);
    return dt.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });
}

// Show loading indicator
function showLoading() {
    const loading = document.createElement('div');
    loading.className = 'loading';
    loading.innerHTML = `
        <div class="spinner-border loading-spinner text-primary" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    `;
    document.body.appendChild(loading);
}

// Hide loading indicator
function hideLoading() {
    const loading = document.querySelector('.loading');
    if (loading) {
        loading.remove();
    }
}

// Show error message
function showError(message) {
    const alertsContainer = document.getElementById('alerts');
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger alert-dismissible fade show';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    alertsContainer.appendChild(alert);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const bsAlert = new bootstrap.Alert(alert);
        bsAlert.close();
    }, 5000);
}

// Show success message
function showSuccess(message) {
    const alertsContainer = document.getElementById('alerts');
    const alert = document.createElement('div');
    alert.className = 'alert alert-success alert-dismissible fade show';
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    alertsContainer.appendChild(alert);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const bsAlert = new bootstrap.Alert(alert);
        bsAlert.close();
    }, 5000);
}

// Create a new user
async function createUser() {
    const email = document.getElementById('userEmail').value;
    
    if (!email) {
        showError('Please enter an email address');
        return;
    }
    
    try {
        showLoading();
        const response = await fetch(`${API_BASE_URL}/agents`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: email
            })
        });

        const result = await response.json();
        hideLoading();

        if (result.status === 'success') {
            showSuccess(result.message);
            
            // Add the new user to select dropdowns
            const agentSelect = document.getElementById('agentSelect');
            const organizerSelect = document.getElementById('meetingOrganizer');
            
            // Add to select elements
            [agentSelect, organizerSelect].forEach(select => {
                const option = new Option(email, email);
                select.add(option);
            });
            
            // Add checkbox to attendees container
            const attendeesContainer = document.getElementById('meetingAttendees');
            const div = document.createElement('div');
            div.className = 'form-check';
            div.innerHTML = `
                <input class="form-check-input attendee-checkbox" type="checkbox" value="${email}" id="attendee-${email}">
                <label class="form-check-label" for="attendee-${email}">
                    ${email}
                </label>
            `;
            attendeesContainer.appendChild(div);
            
            // Close the modal
            bootstrap.Modal.getInstance(document.getElementById('createUserModal')).hide();
            
            // Clear the form
            document.getElementById('userEmail').value = '';
        } else {
            showError(result.message || 'Failed to create user');
        }
    } catch (error) {
        hideLoading();
        showError('Failed to create user: ' + error.message);
    }
}

// Add negotiation dialog HTML
const negotiationDialog = document.createElement('div');
negotiationDialog.className = 'modal fade';
negotiationDialog.id = 'negotiationModal';
negotiationDialog.innerHTML = `
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Meeting Negotiation Required</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="target-meeting-info mb-4 p-3 bg-light border rounded">
                    <h6 class="text-primary mb-3">Target Meeting Details</h6>
                    <div id="targetMeetingTitle" class="fw-bold mb-2"></div>
                    <div id="targetMeetingTime" class="mb-2"></div>
                    <div id="targetMeetingOrganizer" class="mb-2"></div>
                    <div id="targetMeetingAttendees" class="mb-2"></div>
                    <div id="targetMeetingPriority" class="mb-2"></div>
                </div>
                <div class="d-flex align-items-center justify-content-center mb-3">
                    <h6 class="text-primary mb-0">
                        <button type="button" class="btn btn-link btn-sm text-decoration-none p-0 me-2" id="prevConflict" disabled>
                            ←
                        </button>
                        Alternative Proposal <span id="currentConflictIndex">1</span> of <span id="totalConflicts">1</span>
                        <button type="button" class="btn btn-link btn-sm text-decoration-none p-0 ms-2" id="nextConflict" disabled>
                            →
                        </button>
                    </h6>
                </div>
                <div id="proposalStats" class="text-center mb-3">
                    <span class="badge bg-info me-2">Impact Score: <span id="proposalImpactScore">0</span></span>
                    <span class="badge bg-warning">Conflicts to Resolve: <span id="proposalConflictCount">0</span></span>
                </div>
                <div id="negotiationDetails"></div>
                <div class="mt-3">
                    <p>How would you like to proceed?</p>
                    <div class="alert alert-info" role="alert">
                        <i class="bi bi-info-circle me-2"></i>
                        This proposal will reschedule all conflicts shown above. Use the navigation buttons to view alternative proposals with different impact scores.
                    </div>
                    <div class="alert alert-warning" role="alert">
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        Force scheduling will create the meeting without moving any conflicts. This may result in double-booking for some attendees.
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-warning" onclick="forceScheduleMeeting()">Force Schedule</button>
                <button type="button" class="btn btn-primary" onclick="acceptNegotiation()">Accept This Proposal</button>
            </div>
        </div>
    </div>
`;
document.body.appendChild(negotiationDialog);

// Add negotiation state variables
let currentNegotiation = null;
let currentConflictIndex = 0;
let allProposals = [];

// Function to format conflicts for display
function formatConflicts(conflicts) {
    // Create a Map to deduplicate conflicts using meeting ID as key
    const uniqueConflictsMap = new Map();
    
    // First pass: group conflicts by meeting ID
    conflicts.forEach(conflict => {
        if (!uniqueConflictsMap.has(conflict.id)) {
            uniqueConflictsMap.set(conflict.id, {
                ...conflict,
                attendees: [...new Set(conflict.attendees)]  // Ensure unique attendees
            });
        } else {
            // If we see this meeting ID again, merge the attendees
            const existing = uniqueConflictsMap.get(conflict.id);
            existing.attendees = [...new Set([...existing.attendees, ...conflict.attendees])];
        }
    });
    
    // Convert Map to array and generate HTML
    return Array.from(uniqueConflictsMap.values())
        .map(conflict => 
            `<div class="conflict-item mb-3 p-3 border-start border-warning border-3">
                <strong>${conflict.summary}</strong> 
                <span class="badge bg-secondary ms-1">Priority: ${conflict.priority || 'N/A'}</span><br>
                <div class="ms-2 mt-2">
                    <div class="text-danger"><strong>Current time:</strong> ${conflict.start} - ${conflict.end}</div>
                    <div class="text-success"><strong>Will be moved to:</strong> ${conflict.new_slot_start} - ${conflict.new_slot_end}</div>
                    <div class="mt-1"><strong>Attendees:</strong> ${conflict.attendees.join(', ')}</div>
                </div>
            </div>`
        ).join('');
}

// Function to update navigation buttons
function updateNavigationButtons() {
    const prevButton = document.getElementById('prevConflict');
    const nextButton = document.getElementById('nextConflict');
    const hasMultipleProposals = allProposals && allProposals.length > 1;
    
    // Update button states
    prevButton.disabled = currentConflictIndex === 0;
    nextButton.disabled = currentConflictIndex === allProposals.length - 1;
    
    // Update visibility
    prevButton.style.display = hasMultipleProposals ? 'inline-block' : 'none';
    nextButton.style.display = hasMultipleProposals ? 'inline-block' : 'none';
    
    console.log('Navigation button states:', {
        hasMultipleProposals,
        currentIndex: currentConflictIndex,
        totalProposals: allProposals.length,
        buttonStates: {
            prev: { disabled: prevButton.disabled, display: prevButton.style.display },
            next: { disabled: nextButton.disabled, display: nextButton.style.display }
        }
    });
}

// Function to show negotiation dialog
function showNegotiationDialog(proposal) {
    console.log('\n=== Negotiation Dialog Started ===');
    
    // Deduplicate conflicts in the proposal before logging
    if (proposal.conflicts) {
        const uniqueConflictsMap = new Map();
        proposal.conflicts.forEach(conflict => {
            if (!uniqueConflictsMap.has(conflict.id)) {
                uniqueConflictsMap.set(conflict.id, {
                    ...conflict,
                    attendees: [...new Set(conflict.attendees)]
                });
            } else {
                // Merge attendees for duplicate conflicts
                const existing = uniqueConflictsMap.get(conflict.id);
                existing.attendees = [...new Set([...existing.attendees, ...conflict.attendees])];
            }
        });
        proposal.conflicts = Array.from(uniqueConflictsMap.values());
    }
    
    console.log('Raw proposal data:', JSON.stringify(proposal, null, 2));
    
    // Reset state
    currentConflictIndex = 0;
    
    // Initialize proposals array
    if (proposal.proposals && Array.isArray(proposal.proposals)) {
        // Deduplicate conflicts in each proposal
        proposal.proposals = proposal.proposals.map(p => {
            if (p.conflicts) {
                const uniqueConflictsMap = new Map();
                p.conflicts.forEach(conflict => {
                    if (!uniqueConflictsMap.has(conflict.id)) {
                        uniqueConflictsMap.set(conflict.id, {
                            ...conflict,
                            attendees: [...new Set(conflict.attendees)]
                        });
                    } else {
                        const existing = uniqueConflictsMap.get(conflict.id);
                        existing.attendees = [...new Set([...existing.attendees, ...conflict.attendees])];
                    }
                });
                return {
                    ...p,
                    conflicts: Array.from(uniqueConflictsMap.values())
                };
            }
            return p;
        });
        
        console.log('Found proposals array with length:', proposal.proposals.length);
        allProposals = proposal.proposals;
    } else if (proposal.proposal && proposal.total_proposals > 1) {
        console.log('Creating proposals array from single proposal');
        allProposals = [proposal.proposal];
    } else {
        console.log('No proposals array found, using single proposal');
        allProposals = [proposal];
    }
    
    // Set initial proposal
    currentNegotiation = allProposals[0];
    
    console.log('Initialized proposals:', {
        totalProposals: allProposals.length,
        currentIndex: currentConflictIndex,
        currentNegotiation: {
            title: currentNegotiation.title,
            start_time: currentNegotiation.start_time,
            impact_score: currentNegotiation.impact_score,
            conflicts: currentNegotiation.conflicts?.length
        }
    });
    
    // Update the display with the first proposal
    updateNegotiationDisplay();
    
    // Set up navigation button handlers
    document.getElementById('prevConflict').onclick = () => {
        if (currentConflictIndex > 0) {
            currentConflictIndex--;
            currentNegotiation = allProposals[currentConflictIndex];
            updateNegotiationDisplay();
        }
    };
    
    document.getElementById('nextConflict').onclick = () => {
        if (currentConflictIndex < allProposals.length - 1) {
            currentConflictIndex++;
            currentNegotiation = allProposals[currentConflictIndex];
            updateNegotiationDisplay();
        }
    };
    
    updateNavigationButtons();
    
    const modal = new bootstrap.Modal(document.getElementById('negotiationModal'));
    modal.show();
}

// Function to update the negotiation display
function updateNegotiationDisplay() {
    const proposedDateTime = new Date(currentNegotiation.start_time);
    const endDateTime = new Date(proposedDateTime.getTime() + currentNegotiation.duration_minutes * 60000);
    
    // Update proposal count display
    document.getElementById('currentConflictIndex').textContent = (currentConflictIndex + 1).toString();
    document.getElementById('totalConflicts').textContent = allProposals.length.toString();
    
    // Update target meeting details
    document.getElementById('targetMeetingTitle').innerHTML = `Meeting: ${currentNegotiation.title}`;
    document.getElementById('targetMeetingTime').innerHTML = `
        <strong>Found a potential slot at:</strong><br>
        <div class="ms-2">
            <strong>Start:</strong> ${proposedDateTime.toLocaleString('en-US', { 
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                timeZoneName: 'short'
            })}<br>
            <strong>End:</strong> ${endDateTime.toLocaleString('en-US', { 
                hour: 'numeric',
                minute: '2-digit',
                timeZoneName: 'short'
            })}
        </div>
    `;
    document.getElementById('targetMeetingOrganizer').innerHTML = `Organizer: ${currentNegotiation.organizer}`;
    document.getElementById('targetMeetingAttendees').innerHTML = `Attendees: ${currentNegotiation.attendees.join(', ')}`;
    document.getElementById('targetMeetingPriority').innerHTML = `Priority: <span class="badge bg-secondary">${currentNegotiation.priority}</span>`;
    
    // Update proposal statistics
    document.getElementById('proposalImpactScore').textContent = currentNegotiation.impact_score.toFixed(1);
    document.getElementById('proposalConflictCount').textContent = currentNegotiation.conflicts.length;
    
    // Update conflicts details
    const details = document.getElementById('negotiationDetails');
    if (currentNegotiation.conflicts.length > 0) {
        details.innerHTML = `
            <h6 class="text-primary mb-3">All Conflicts in This Proposal:</h6>
            ${formatConflicts(currentNegotiation.conflicts)}
            <div class="affected-attendees mt-3">
                <h6 class="text-primary">Total Affected Attendees:</h6>
                <p>${currentNegotiation.affected_attendees.join(', ')}</p>
            </div>
        `;
    } else {
        details.innerHTML = `
            <div class="alert alert-success" role="alert">
                <i class="bi bi-check-circle me-2"></i>
                This proposal has no conflicts! All attendees are available at the proposed time.
            </div>
        `;
    }
    
    updateNavigationButtons();
}

// Function to handle negotiation acceptance
async function acceptNegotiation() {
    if (!currentNegotiation) return;
    
    try {
        showLoading();
        const response = await fetch(`${API_BASE_URL}/agents/${currentNegotiation.organizer}/negotiate?proposal_id=${currentNegotiation.id}&action=accept`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();
        hideLoading();

        if (result.status === 'success') {
            let message = `Meeting '${currentNegotiation.title}' (Priority: ${currentNegotiation.priority || 'N/A'}) has been successfully scheduled.\n\n`;
            
            if (result.rescheduled_meetings && result.rescheduled_meetings.length > 0) {
                const uniqueMeetingsMap = new Map();
                result.rescheduled_meetings.forEach(meeting => {
                    uniqueMeetingsMap.set(meeting.id, meeting);
                });

                message += 'Rescheduled meetings:\n';
                Array.from(uniqueMeetingsMap.values()).forEach(meeting => {
                    message += `\n• "${meeting.title}" (Priority: ${meeting.priority || 'N/A'})\n`;
                    message += `  From: ${meeting.original_time}\n`;
                    message += `  To: ${meeting.new_time}\n`;
                    message += `  Attendees: ${meeting.attendees.map(a => a.email).join(', ')}\n`;
                });
            }
            
            showSuccess(message.replace(/\n/g, '<br>'));
            
            const selectedAgent = document.getElementById('agentSelect').value;
            if (selectedAgent) {
                await onAgentSelect(selectedAgent);
            }
        } else {
            showError(result.message || 'Failed to reschedule meeting');
        }
    } catch (error) {
        hideLoading();
        showError('Failed to process negotiation: ' + error.message);
    } finally {
        currentNegotiation = null;
        const modal = bootstrap.Modal.getInstance(document.getElementById('negotiationModal'));
        if (modal) {
            modal.hide();
        }
    }
}

// Add the force schedule function
async function forceScheduleMeeting() {
    if (!currentNegotiation) return;
    
    try {
        showLoading();
        const response = await fetch(`${API_BASE_URL}/agents/${currentNegotiation.organizer}/negotiate?proposal_id=${currentNegotiation.id}&action=force`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();
        hideLoading();

        if (result.status === 'success') {
            showSuccess(`Meeting '${currentNegotiation.title}' has been force scheduled. Some attendees may have conflicts.`);
            
            const selectedAgent = document.getElementById('agentSelect').value;
            if (selectedAgent) {
                await onAgentSelect(selectedAgent);
            }
        } else {
            showError(result.message || 'Failed to force schedule meeting');
        }
    } catch (error) {
        hideLoading();
        showError('Failed to force schedule meeting: ' + error.message);
    } finally {
        currentNegotiation = null;
        const modal = bootstrap.Modal.getInstance(document.getElementById('negotiationModal'));
        if (modal) {
            modal.hide();
        }
    }
}

// Schedule a new meeting
async function scheduleMeeting() {
    // Get form values
    const title = document.getElementById('meetingTitle').value;
    const organizer = document.getElementById('meetingOrganizer').value;
    const attendees = Array.from(document.querySelectorAll('.attendee-checkbox:checked')).map(cb => cb.value);
    const startDate = document.getElementById('meetingStartDate').value;
    const endDate = document.getElementById('meetingEndDate').value;
    const duration = document.getElementById('meetingDuration').value;
    const priorityValue = document.getElementById('meetingPriority').value;
    const description = document.getElementById('meetingDescription').value;

    // Validate required fields
    if (!title || !organizer || attendees.length === 0 || !startDate || !endDate || !duration || !priorityValue) {
        showError('Please fill in all required fields');
        return;
    }

    try {
        showLoading();

        // If priority is "auto", first get the evaluated priority
        let priority;
        if (priorityValue === 'auto') {
            // Create a mock event to evaluate priority
            const mockEvent = {
                summary: title,
                description: description,
                attendees: attendees.map(email => ({ email })),
                recurrence: null  // Add recurrence if needed
            };

            // Get evaluated priority from server
            const evalResponse = await fetch(`${API_BASE_URL}/agents/${organizer}/evaluate_priority`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(mockEvent)
            });

            if (!evalResponse.ok) {
                throw new Error('Failed to evaluate priority');
            }

            const evalResult = await evalResponse.json();
            priority = evalResult.priority;
        } else {
            priority = parseInt(priorityValue);
        }

        // Create date range in local timezone
        const startDateTime = new Date(`${startDate}T00:00:00`);
        const endDateTime = new Date(`${endDate}T23:59:59`);

        // Get timezone offset in minutes
        const tzOffset = startDateTime.getTimezoneOffset();

        // Create new dates without modifying for timezone
        const isoStartDate = new Date(startDateTime.getFullYear(), startDateTime.getMonth(), startDateTime.getDate(), 0, 0, 0).toISOString();
        const isoEndDate = new Date(endDateTime.getFullYear(), endDateTime.getMonth(), endDateTime.getDate(), 23, 59, 59).toISOString();

        // Schedule the meeting with the determined priority
        const response = await fetch(`${API_BASE_URL}/agents/${organizer}/meetings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title,
                duration_minutes: parseInt(duration),
                organizer,
                attendees,
                priority,
                description,
                preferred_time_ranges: [
                    [isoStartDate, isoEndDate]
                ]
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText);
        }

        const result = await response.json();
        hideLoading();

        if (result.status === 'success') {
            let message = "";
            if (result.event) {
                let scheduledTime = "Unknown";
                if (result.event.start) {
                    let dateCandidate;
                    if (result.event.start.dateTime) {
                        dateCandidate = new Date(result.event.start.dateTime);
                    } else if (result.event.start.date) {
                        dateCandidate = new Date(result.event.start.date);
                    } else {
                        dateCandidate = new Date(result.event.start);
                    }
                    if (!isNaN(dateCandidate.getTime())) {
                        scheduledTime = dateCandidate.toLocaleString();
                    }
                }
                message = `Meeting '${result.event.summary}' is scheduled at: ${scheduledTime}`;
            } else {
                message = 'Meeting scheduled successfully';
            }
            showSuccess(message);
            // Close the modal
            bootstrap.Modal.getInstance(document.getElementById('scheduleMeetingModal')).hide();
            // Refresh the calendar if an agent is selected
            const selectedAgent = document.getElementById('agentSelect').value;
            if (selectedAgent) {
                await onAgentSelect(selectedAgent);
            }
        } else if (result.status === 'needs_negotiation') {
            // Close the scheduling modal
            bootstrap.Modal.getInstance(document.getElementById('scheduleMeetingModal')).hide();
            
            // Log the negotiation response
            console.log('Negotiation response:', result);
            
            // Show negotiation dialog with the complete result object
            showNegotiationDialog(result);
        } else {
            showError(result.message || 'Failed to schedule meeting');
        }
    } catch (error) {
        hideLoading();
        showError('Failed to schedule meeting: ' + error.message);
    }
} 