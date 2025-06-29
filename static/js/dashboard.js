/**
 * Sprint Planning Dashboard Manager
 */

class DashboardManager {
    constructor() {
        this.currentSprint = null;
        this.sprinters = [];
        this.tasks = [];
        this.taskIdCounter = 1;
        this.capacityData = {};
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadDashboardData();
    }

    bindEvents() {
        // Task drag and drop events
        document.addEventListener('taskMoved', this.handleTaskMoved.bind(this));
        document.addEventListener('dragStart', this.handleDragStart.bind(this));
        
        // Window events
        window.addEventListener('beforeunload', this.saveState.bind(this));
        
        // Auto-save every 30 seconds
        setInterval(() => {
            this.autoSave();
        }, 30000);
    }

    async loadDashboardData() {
        try {
            // Check if we have sprint data in session storage
            const savedData = sessionStorage.getItem('sprintPlanningData');
            if (savedData) {
                const data = JSON.parse(savedData);
                this.currentSprint = data.currentSprint;
                this.sprinters = data.sprinters;
                this.capacityData = data.capacityData;
                
                // Load planning tasks if planning list ID is available
                if (data.planningListId) {
                    await this.loadPlanningTasks(data.planningListId);
                }
                
                this.renderDashboard();
            } else {
                // Redirect to setup if no data
                this.showSetupRequired();
            }
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showError('Failed to load sprint data. Please check your setup.');
        }
    }

    async loadPlanningTasks(planningListId) {
        try {
            const response = await fetch('/get-planning-tasks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    planning_list_id: planningListId
                })
            });

            const data = await response.json();

            if (data.success) {
                // Add unique IDs and load into tasks array
                data.tasks.forEach((task, index) => {
                    task.id = `trello-${task.id}`;  // Prefix to avoid conflicts
                    task.createdAt = new Date().toISOString();
                });
                
                this.tasks = data.tasks;
                this.taskIdCounter = this.tasks.length + 1;
                
                console.log(`Loaded ${data.tasks.length} planning tasks from Trello`);
            } else {
                console.error('Failed to load planning tasks:', data.error);
                this.showError('Failed to load planning tasks: ' + data.error);
            }
        } catch (error) {
            console.error('Error loading planning tasks:', error);
            this.showError('Failed to load planning tasks from Trello.');
        }
    }

    showSetupRequired() {
        const content = document.getElementById('planning-content');
        content.innerHTML = `
            <div style="text-align: center; padding: 60px 20px;">
                <div style="font-size: 48px; margin-bottom: 16px;">⚙️</div>
                <h3 style="margin-bottom: 12px; color: #2d3748;">Setup Required</h3>
                <p style="color: #718096; margin-bottom: 24px;">
                    Please complete the sprint analysis and capacity planning setup first.
                </p>
                <button class="nav-button" onclick="goToSetup()">
                    Go to Setup
                </button>
            </div>
        `;
    }

    renderDashboard() {
        if (!this.sprinters.length) {
            this.showSetupRequired();
            return;
        }

        // Update header info
        document.getElementById('current-sprint').textContent = `Sprint ${this.currentSprint}`;
        
        // Calculate total capacity
        const totalCapacity = Object.values(this.capacityData).reduce((sum, cap) => sum + cap.suggested_sp, 0);
        document.getElementById('total-capacity').textContent = totalCapacity;
        
        // Render sprinters grid
        this.renderSprintersGrid();
        
        // Update capacity displays
        this.updateCapacityDisplays();
        
        // Render backlog with loaded tasks
        this.renderBacklog();
        
        // Enable drag and drop
        if (window.sprintDragDrop) {
            window.sprintDragDrop.enableDragDrop();
        }
    }

    renderSprintersGrid() {
        const content = document.getElementById('planning-content');
        
        let html = '<div class="sprinters-grid">';
        
        this.sprinters.forEach(sprinter => {
            const capacity = this.capacityData[sprinter.id] || { suggested_sp: 0 };
            const assignedTasks = this.getAssignedTasks(sprinter.id);
            const assignedSP = assignedTasks.reduce((sum, task) => sum + task.sp, 0);
            const realUtilizationPercent = capacity.suggested_sp > 0 ? 
                Math.round((assignedSP / capacity.suggested_sp) * 100) : 0;
            const targetUtilizationPercent = capacity.target_sp_per_person > 0 ? 
                Math.round((assignedSP / capacity.target_sp_per_person) * 100) : 0;
            
            html += `
                <div class="sprinter-column" id="sprinter-${sprinter.id}" data-sprinter-id="${sprinter.id}">
                    <div class="sprinter-header">
                        <div class="sprinter-name">${sprinter.name}</div>
                        <div class="sprinter-capacity">
                            <div class="capacity-text">${assignedSP}/${capacity.suggested_sp} SP</div>
                            <div class="capacity-bar">
                                <div class="capacity-fill" style="width: ${Math.min(realUtilizationPercent, 100)}%"></div>
                            </div>
                            <div class="utilization-info">
                                <span class="real-util">Reel: ${realUtilizationPercent}%</span>
                                <span class="target-util">Hedef: ${targetUtilizationPercent}%</span>
                            </div>
                        </div>
                    </div>
                    <div class="tasks-list" id="tasks-${sprinter.id}">
                        ${this.renderAssignedTasks(assignedTasks)}
                    </div>
                    ${assignedTasks.length === 0 ? '<div class="empty-column">Drop tasks here</div>' : ''}
                </div>
            `;
        });
        
        html += '</div>';
        content.innerHTML = html;
    }

    renderAssignedTasks(tasks) {
        return tasks.map(task => this.renderTask(task, 'assigned')).join('');
    }

    renderTask(task, type = 'backlog') {
        const taskClass = type === 'backlog' ? 'backlog-task' : 'assigned-task';
        const priorityClass = `priority-${task.priority}`;
        
        return `
            <div class="${taskClass} ${priorityClass}" 
                 data-task-id="${task.id}" 
                 data-priority="${task.priority}"
                 data-description="${task.description || ''}"
                 title="${task.description || ''}">
                <div class="task-priority priority-${task.priority}"></div>
                <div class="task-title">${task.title}</div>
                <div class="task-meta">
                    <span class="task-sp">${task.sp} SP</span>
                    <span class="task-priority-text">${this.getPriorityText(task.priority)}</span>
                    ${task.url ? `<a href="${task.url}" target="_blank" title="Open in Trello" style="color: #3182ce; text-decoration: none; margin-left: 8px;">🔗</a>` : ''}
                </div>
                ${type === 'assigned' ? `
                    <div class="task-actions">
                        <button class="task-action-btn" onclick="editTask('${task.id}')" title="Edit">✏️</button>
                        <button class="task-action-btn delete" onclick="deleteTask('${task.id}')" title="Delete">🗑️</button>
                        ${task.url ? `<button class="task-action-btn" onclick="window.open('${task.url}', '_blank')" title="Open in Trello">🔗</button>` : ''}
                    </div>
                ` : ''}
            </div>
        `;
    }

    getPriorityText(priority) {
        const priorities = {
            high: 'High',
            medium: 'Medium',
            low: 'Low'
        };
        return priorities[priority] || 'Medium';
    }

    getAssignedTasks(sprinterId) {
        return this.tasks.filter(task => task.assignedTo === sprinterId);
    }

    handleTaskMoved(event) {
        const { task, sourceContainer, targetContainer } = event.detail;
        
        // Update task assignment
        const taskObj = this.tasks.find(t => t.id === task.id);
        if (!taskObj) return;
        
        if (targetContainer.startsWith('sprinter-')) {
            const sprinterId = targetContainer.replace('sprinter-', '');
            taskObj.assignedTo = sprinterId;
        } else if (targetContainer === 'backlog-list') {
            taskObj.assignedTo = null;
        }
        
        // Update displays
        this.updateCapacityDisplays();
        this.updateBacklogCount();
        
        // Save state
        this.saveState();
        
        // Show feedback
        this.showTaskMovedFeedback(task, sourceContainer, targetContainer);
    }

    handleDragStart(event) {
        // Add visual feedback for drag start
        document.body.classList.add('dragging-active');
    }

    showTaskMovedFeedback(task, source, target) {
        const isAssignment = target.startsWith('sprinter-');
        const isUnassignment = source.startsWith('sprinter-') && target === 'backlog-list';
        
        let message = '';
        if (isAssignment) {
            const sprinterId = target.replace('sprinter-', '');
            const sprinter = this.sprinters.find(s => s.id === sprinterId);
            message = `Task "${task.title}" assigned to ${sprinter?.name}`;
        } else if (isUnassignment) {
            message = `Task "${task.title}" moved back to backlog`;
        }
        
        if (message) {
            this.showAlert(message, 'success', 3000);
        }
    }

    updateCapacityDisplays() {
        // Update individual sprinter capacities
        this.sprinters.forEach(sprinter => {
            const capacity = this.capacityData[sprinter.id] || { suggested_sp: 0, target_sp_per_person: 21 };
            const assignedTasks = this.getAssignedTasks(sprinter.id);
            const assignedSP = assignedTasks.reduce((sum, task) => sum + task.sp, 0);
            const realUtilizationPercent = capacity.suggested_sp > 0 ? 
                Math.round((assignedSP / capacity.suggested_sp) * 100) : 0;
            const targetUtilizationPercent = capacity.target_sp_per_person > 0 ? 
                Math.round((assignedSP / capacity.target_sp_per_person) * 100) : 0;
            
            // Update capacity text
            const capacityText = document.querySelector(`#sprinter-${sprinter.id} .capacity-text`);
            if (capacityText) {
                capacityText.textContent = `${assignedSP}/${capacity.suggested_sp} SP`;
            }
            
            // Update capacity bar
            const capacityFill = document.querySelector(`#sprinter-${sprinter.id} .capacity-fill`);
            if (capacityFill) {
                capacityFill.style.width = `${Math.min(realUtilizationPercent, 100)}%`;
            }
            
            // Update utilization info
            const realUtilElement = document.querySelector(`#sprinter-${sprinter.id} .real-util`);
            if (realUtilElement) {
                realUtilElement.textContent = `Reel: ${realUtilizationPercent}%`;
            }
            
            const targetUtilElement = document.querySelector(`#sprinter-${sprinter.id} .target-util`);
            if (targetUtilElement) {
                targetUtilElement.textContent = `Hedef: ${targetUtilizationPercent}%`;
            }
            
            // Update empty state
            const emptyColumn = document.querySelector(`#sprinter-${sprinter.id} .empty-column`);
            if (emptyColumn) {
                emptyColumn.style.display = assignedTasks.length === 0 ? 'flex' : 'none';
            }
        });
        
        // Update global summary
        const totalCapacity = Object.values(this.capacityData).reduce((sum, cap) => sum + cap.suggested_sp, 0);
        const totalTargetCapacity = Object.values(this.capacityData).reduce((sum, cap) => sum + (cap.target_sp_per_person || 21), 0);
        const totalAssigned = this.tasks
            .filter(task => task.assignedTo)
            .reduce((sum, task) => sum + task.sp, 0);
        const teamRealUtilization = totalCapacity > 0 ? Math.round((totalAssigned / totalCapacity) * 100) : 0;
        const teamTargetUtilization = totalTargetCapacity > 0 ? Math.round((totalAssigned / totalTargetCapacity) * 100) : 0;
        const remainingCapacity = totalCapacity - totalAssigned;
        const assignedTaskCount = this.tasks.filter(task => task.assignedTo).length;
        
        document.getElementById('assigned-capacity').textContent = totalAssigned;
        document.getElementById('team-utilization').textContent = `R:${teamRealUtilization}% H:${teamTargetUtilization}%`;
        document.getElementById('remaining-capacity').textContent = remainingCapacity;
        document.getElementById('task-count').textContent = assignedTaskCount;
    }

    updateBacklogCount() {
        const backlogTasks = this.tasks.filter(task => !task.assignedTo);
        document.getElementById('backlog-count').textContent = backlogTasks.length;
        
        // Re-render backlog
        this.renderBacklog();
    }

    renderBacklog() {
        const backlogList = document.getElementById('backlog-list');
        const backlogTasks = this.tasks.filter(task => !task.assignedTo);
        
        if (backlogTasks.length === 0) {
            backlogList.innerHTML = '<div style="text-align: center; color: #a0aec0; padding: 20px;">No tasks in backlog</div>';
        } else {
            backlogList.innerHTML = backlogTasks
                .sort((a, b) => this.getPriorityOrder(a.priority) - this.getPriorityOrder(b.priority))
                .map(task => this.renderTask(task, 'backlog'))
                .join('');
        }
    }

    getPriorityOrder(priority) {
        const orders = { high: 1, medium: 2, low: 3 };
        return orders[priority] || 2;
    }

    saveState() {
        const state = {
            currentSprint: this.currentSprint,
            sprinters: this.sprinters,
            capacityData: this.capacityData,
            tasks: this.tasks,
            lastSaved: new Date().toISOString()
        };
        
        sessionStorage.setItem('sprintPlanningData', JSON.stringify(state));
        localStorage.setItem(`sprint_${this.currentSprint}_tasks`, JSON.stringify(this.tasks));
    }

    autoSave() {
        this.saveState();
        this.showAlert('Auto-saved', 'info', 1000);
    }

    showAlert(message, type = 'info', duration = 5000) {
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.textContent = message;
        alert.style.position = 'fixed';
        alert.style.top = '100px';
        alert.style.right = '20px';
        alert.style.zIndex = '1001';
        alert.style.minWidth = '200px';
        alert.style.opacity = '0';
        alert.style.transition = 'opacity 0.3s ease';
        
        document.body.appendChild(alert);
        
        // Animate in
        setTimeout(() => {
            alert.style.opacity = '1';
        }, 10);
        
        // Remove after duration
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => {
                if (alert.parentElement) {
                    alert.parentElement.removeChild(alert);
                }
            }, 300);
        }, duration);
    }

    showError(message) {
        this.showAlert(message, 'error');
    }
}

// Task Management Functions
function addTask(event) {
    event.preventDefault();
    
    const title = document.getElementById('task-title').value.trim();
    const sp = parseInt(document.getElementById('task-sp').value);
    const priority = document.getElementById('task-priority').value;
    const description = document.getElementById('task-description').value.trim();
    
    if (!title || !sp) {
        window.dashboardManager.showError('Please fill in task title and story points');
        return;
    }
    
    const task = {
        id: `task-${window.dashboardManager.taskIdCounter++}`,
        title,
        sp,
        priority,
        description,
        assignedTo: null,
        createdAt: new Date().toISOString()
    };
    
    window.dashboardManager.tasks.push(task);
    window.dashboardManager.updateBacklogCount();
    window.dashboardManager.saveState();
    
    // Clear form
    document.getElementById('task-title').value = '';
    document.getElementById('task-sp').value = '';
    document.getElementById('task-description').value = '';
    document.getElementById('task-priority').value = 'medium';
    
    window.dashboardManager.showAlert(`Task "${title}" added to backlog`, 'success');
}

function editTask(taskId) {
    const task = window.dashboardManager.tasks.find(t => t.id === taskId);
    if (!task) return;
    
    // Simple prompt-based editing (can be enhanced with modal)
    const newTitle = prompt('Edit task title:', task.title);
    if (newTitle && newTitle.trim()) {
        task.title = newTitle.trim();
        
        const newSP = prompt('Edit story points:', task.sp);
        if (newSP && !isNaN(newSP)) {
            task.sp = parseInt(newSP);
        }
        
        window.dashboardManager.renderDashboard();
        window.dashboardManager.saveState();
        window.dashboardManager.showAlert('Task updated', 'success');
    }
}

function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) return;
    
    const taskIndex = window.dashboardManager.tasks.findIndex(t => t.id === taskId);
    if (taskIndex === -1) return;
    
    const task = window.dashboardManager.tasks[taskIndex];
    window.dashboardManager.tasks.splice(taskIndex, 1);
    
    window.dashboardManager.renderDashboard();
    window.dashboardManager.updateBacklogCount();
    window.dashboardManager.saveState();
    
    window.dashboardManager.showAlert(`Task "${task.title}" deleted`, 'success');
}

function autoAssignTasks() {
    // Simple auto-assignment algorithm
    const unassignedTasks = window.dashboardManager.tasks
        .filter(task => !task.assignedTo)
        .sort((a, b) => window.dashboardManager.getPriorityOrder(a.priority) - window.dashboardManager.getPriorityOrder(b.priority));
    
    if (unassignedTasks.length === 0) {
        window.dashboardManager.showAlert('No unassigned tasks to assign', 'info');
        return;
    }
    
    let assigned = 0;
    
    unassignedTasks.forEach(task => {
        // Find sprinter with lowest current load
        let bestSprinter = null;
        let lowestLoad = Infinity;
        
        window.dashboardManager.sprinters.forEach(sprinter => {
            const capacity = window.dashboardManager.capacityData[sprinter.id] || { suggested_sp: 0 };
            const currentLoad = window.dashboardManager.getAssignedTasks(sprinter.id)
                .reduce((sum, t) => sum + t.sp, 0);
            
            if (currentLoad + task.sp <= capacity.suggested_sp && currentLoad < lowestLoad) {
                lowestLoad = currentLoad;
                bestSprinter = sprinter;
            }
        });
        
        if (bestSprinter) {
            task.assignedTo = bestSprinter.id;
            assigned++;
        }
    });
    
    window.dashboardManager.renderDashboard();
    window.dashboardManager.updateBacklogCount();
    window.dashboardManager.saveState();
    
    window.dashboardManager.showAlert(`Auto-assigned ${assigned} tasks`, 'success');
}

function toggleExportMenu() {
    const menu = document.getElementById('export-menu');
    menu.classList.toggle('hidden');
    
    // Close menu when clicking outside
    if (!menu.classList.contains('hidden')) {
        setTimeout(() => {
            document.addEventListener('click', function closeMenu(e) {
                if (!e.target.closest('#export-menu') && !e.target.closest('[onclick="toggleExportMenu()"]')) {
                    menu.classList.add('hidden');
                    document.removeEventListener('click', closeMenu);
                }
            });
        }, 10);
    }
}

function exportSprint(format = 'json') {
    const data = {
        sprint: window.dashboardManager.currentSprint,
        sprinters: window.dashboardManager.sprinters,
        tasks: window.dashboardManager.tasks,
        capacityData: window.dashboardManager.capacityData,
        exportedAt: new Date().toISOString()
    };
    
    // Close export menu
    document.getElementById('export-menu').classList.add('hidden');
    
    switch (format) {
        case 'json':
            exportAsJSON(data);
            break;
        case 'csv':
            exportAsCSV(data);
            break;
        case 'png':
            exportAsPNG();
            break;
        default:
            exportAsJSON(data);
    }
}

function exportAsJSON(data) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sprint-${window.dashboardManager.currentSprint}-plan.json`;
    a.click();
    URL.revokeObjectURL(url);
    
    window.dashboardManager.showAlert('Sprint plan exported as JSON', 'success');
}

function exportAsCSV(data) {
    let csv = 'Task ID,Title,Story Points,Priority,Assigned To,Status\n';
    
    data.tasks.forEach(task => {
        const assignedTo = task.assignedTo ? 
            data.sprinters.find(s => s.id === task.assignedTo)?.name || 'Unknown' : 
            'Unassigned';
        
        const status = task.assignedTo ? 'Assigned' : 'Backlog';
        
        csv += `"${task.id}","${task.title}",${task.sp},"${task.priority}","${assignedTo}","${status}"\n`;
    });
    
    // Add capacity summary
    csv += '\n\nSprinter,Suggested Capacity,Assigned SP,Real Utilization,Target Utilization\n';
    data.sprinters.forEach(sprinter => {
        const capacity = data.capacityData[sprinter.id];
        const assignedTasks = data.tasks.filter(t => t.assignedTo === sprinter.id);
        const assignedSP = assignedTasks.reduce((sum, t) => sum + t.sp, 0);
        const realUtilization = capacity.suggested_sp > 0 ? 
            Math.round((assignedSP / capacity.suggested_sp) * 100) : 0;
        const targetUtilization = capacity.target_sp_per_person > 0 ? 
            Math.round((assignedSP / capacity.target_sp_per_person) * 100) : 0;
        
        csv += `"${sprinter.name}",${capacity.suggested_sp},${assignedSP},${realUtilization}%,${targetUtilization}%\n`;
    });
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sprint-${window.dashboardManager.currentSprint}-plan.csv`;
    a.click();
    URL.revokeObjectURL(url);
    
    window.dashboardManager.showAlert('Sprint plan exported as CSV', 'success');
}

function exportAsPNG() {
    // Create a canvas to render the sprint plan
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 1200;
    canvas.height = 800;
    
    // Set background
    ctx.fillStyle = '#fafafa';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Title
    ctx.fillStyle = '#1a202c';
    ctx.font = 'bold 24px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.fillText(`Sprint ${window.dashboardManager.currentSprint} Planning`, 40, 50);
    
    // Sprint info
    ctx.fillStyle = '#4a5568';
    ctx.font = '14px -apple-system, BlinkMacSystemFont, sans-serif';
    const totalCapacity = Object.values(window.dashboardManager.capacityData).reduce((sum, cap) => sum + cap.suggested_sp, 0);
    const totalAssigned = window.dashboardManager.tasks
        .filter(task => task.assignedTo)
        .reduce((sum, task) => sum + task.sp, 0);
    
    ctx.fillText(`Total Capacity: ${totalCapacity} SP | Assigned: ${totalAssigned} SP`, 40, 80);
    
    // Sprinters
    let yPos = 120;
    const colWidth = 280;
    const cols = Math.floor((canvas.width - 80) / colWidth);
    
    window.dashboardManager.sprinters.forEach((sprinter, index) => {
        const col = index % cols;
        const row = Math.floor(index / cols);
        const x = 40 + (col * colWidth);
        const y = yPos + (row * 200);
        
        // Sprinter box
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(x, y, colWidth - 20, 180);
        ctx.strokeStyle = '#e2e8f0';
        ctx.strokeRect(x, y, colWidth - 20, 180);
        
        // Sprinter name
        ctx.fillStyle = '#2d3748';
        ctx.font = 'bold 16px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.fillText(sprinter.name, x + 10, y + 25);
        
        // Capacity info
        const capacity = window.dashboardManager.capacityData[sprinter.id];
        const assignedTasks = window.dashboardManager.getAssignedTasks(sprinter.id);
        const assignedSP = assignedTasks.reduce((sum, task) => sum + task.sp, 0);
        
        ctx.fillStyle = '#4a5568';
        ctx.font = '12px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.fillText(`Capacity: ${assignedSP}/${capacity.suggested_sp} SP`, x + 10, y + 45);
        
        // Capacity bar
        const barWidth = colWidth - 40;
        const barHeight = 8;
        ctx.fillStyle = '#e2e8f0';
        ctx.fillRect(x + 10, y + 55, barWidth, barHeight);
        
        const fillWidth = capacity.suggested_sp > 0 ? 
            (assignedSP / capacity.suggested_sp) * barWidth : 0;
        ctx.fillStyle = '#3182ce';
        ctx.fillRect(x + 10, y + 55, Math.min(fillWidth, barWidth), barHeight);
        
        // Tasks
        let taskY = y + 75;
        assignedTasks.slice(0, 8).forEach(task => {
            ctx.fillStyle = '#f7fafc';
            ctx.fillRect(x + 10, taskY, colWidth - 40, 20);
            ctx.strokeStyle = '#e2e8f0';
            ctx.strokeRect(x + 10, taskY, colWidth - 40, 20);
            
            ctx.fillStyle = '#2d3748';
            ctx.font = '11px -apple-system, BlinkMacSystemFont, sans-serif';
            const taskText = task.title.length > 25 ? task.title.substring(0, 25) + '...' : task.title;
            ctx.fillText(`${taskText} (${task.sp} SP)`, x + 15, taskY + 14);
            
            taskY += 25;
        });
        
        if (assignedTasks.length > 8) {
            ctx.fillStyle = '#718096';
            ctx.font = '10px -apple-system, BlinkMacSystemFont, sans-serif';
            ctx.fillText(`+${assignedTasks.length - 8} more tasks`, x + 15, taskY + 10);
        }
    });
    
    // Convert to blob and download
    canvas.toBlob(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `sprint-${window.dashboardManager.currentSprint}-plan.png`;
        a.click();
        URL.revokeObjectURL(url);
        
        window.dashboardManager.showAlert('Sprint plan exported as PNG', 'success');
    }, 'image/png');
}

function goToSetup() {
    window.location.href = '/';
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboardManager = new DashboardManager();
});