/**
 * Drag and Drop Functionality for Sprint Planning
 */

class SprintDragDrop {
    constructor() {
        this.draggedElement = null;
        this.sourceContainer = null;
        this.touchStartPos = { x: 0, y: 0 };
        this.isDragging = false;
        
        this.init();
    }

    init() {
        // Initialize drag and drop event listeners
        this.bindEvents();
    }

    bindEvents() {
        // Mouse events
        document.addEventListener('mousedown', this.handleMouseDown.bind(this));
        document.addEventListener('mousemove', this.handleMouseMove.bind(this));
        document.addEventListener('mouseup', this.handleMouseUp.bind(this));
        
        // Touch events for mobile
        document.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: false });
        document.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: false });
        document.addEventListener('touchend', this.handleTouchEnd.bind(this));
        
        // Prevent default drag behavior on images and other elements
        document.addEventListener('dragstart', (e) => e.preventDefault());
    }

    handleMouseDown(e) {
        const task = e.target.closest('.backlog-task, .assigned-task');
        if (!task) return;

        this.startDrag(task, e.clientX, e.clientY);
    }

    handleMouseMove(e) {
        if (!this.isDragging) return;
        
        e.preventDefault();
        this.updateDragPosition(e.clientX, e.clientY);
        this.updateDropZones(e.clientX, e.clientY);
    }

    handleMouseUp(e) {
        if (!this.isDragging) return;
        
        this.endDrag(e.clientX, e.clientY);
    }

    handleTouchStart(e) {
        if (e.touches.length !== 1) return;
        
        const touch = e.touches[0];
        const task = e.target.closest('.backlog-task, .assigned-task');
        if (!task) return;

        this.touchStartPos = { x: touch.clientX, y: touch.clientY };
        
        // Delay to distinguish between tap and drag
        setTimeout(() => {
            if (this.touchStartPos) {
                this.startDrag(task, touch.clientX, touch.clientY);
            }
        }, 150);
    }

    handleTouchMove(e) {
        if (!this.touchStartPos) return;
        
        const touch = e.touches[0];
        const deltaX = Math.abs(touch.clientX - this.touchStartPos.x);
        const deltaY = Math.abs(touch.clientY - this.touchStartPos.y);
        
        // If significant movement, start dragging
        if ((deltaX > 10 || deltaY > 10) && !this.isDragging) {
            const task = e.target.closest('.backlog-task, .assigned-task');
            if (task) {
                e.preventDefault();
                this.startDrag(task, touch.clientX, touch.clientY);
            }
        }
        
        if (this.isDragging) {
            e.preventDefault();
            this.updateDragPosition(touch.clientX, touch.clientY);
            this.updateDropZones(touch.clientX, touch.clientY);
        }
    }

    handleTouchEnd(e) {
        this.touchStartPos = null;
        
        if (!this.isDragging) return;
        
        const touch = e.changedTouches[0];
        this.endDrag(touch.clientX, touch.clientY);
    }

    startDrag(task, x, y) {
        this.draggedElement = task;
        this.sourceContainer = task.parentElement;
        this.isDragging = true;
        
        // Add dragging class
        task.classList.add('dragging');
        
        // Create drag preview
        this.createDragPreview(task, x, y);
        
        // Update cursor
        document.body.style.cursor = 'grabbing';
        
        // Add drop zone highlights
        this.highlightDropZones();
        
        // Trigger drag start event
        this.triggerEvent('dragStart', {
            task: this.getTaskData(task),
            sourceContainer: this.sourceContainer.id
        });
    }

    createDragPreview(task, x, y) {
        const preview = task.cloneNode(true);
        preview.id = 'drag-preview';
        preview.style.position = 'fixed';
        preview.style.pointerEvents = 'none';
        preview.style.zIndex = '1000';
        preview.style.opacity = '0.8';
        preview.style.transform = 'rotate(5deg) scale(1.05)';
        preview.style.transition = 'none';
        preview.style.left = x - 50 + 'px';
        preview.style.top = y - 20 + 'px';
        preview.style.width = task.offsetWidth + 'px';
        
        document.body.appendChild(preview);
    }

    updateDragPosition(x, y) {
        const preview = document.getElementById('drag-preview');
        if (preview) {
            preview.style.left = x - 50 + 'px';
            preview.style.top = y - 20 + 'px';
        }
    }

    updateDropZones(x, y) {
        // Remove previous highlights
        document.querySelectorAll('.sprinter-column').forEach(col => {
            col.classList.remove('drag-over');
        });
        
        // Find element under cursor
        const elementBelow = document.elementFromPoint(x, y);
        const dropZone = elementBelow?.closest('.sprinter-column, .backlog');
        
        if (dropZone && dropZone !== this.sourceContainer) {
            dropZone.classList.add('drag-over');
        }
    }

    endDrag(x, y) {
        if (!this.isDragging) return;
        
        // Find drop target
        const elementBelow = document.elementFromPoint(x, y);
        const dropTarget = elementBelow?.closest('.sprinter-column, .backlog');
        
        // Clean up
        this.cleanupDrag();
        
        if (dropTarget && dropTarget !== this.sourceContainer) {
            this.handleDrop(dropTarget);
        } else {
            // Return to original position with animation
            this.returnToSource();
        }
        
        this.isDragging = false;
        this.draggedElement = null;
        this.sourceContainer = null;
    }

    handleDrop(dropTarget) {
        const taskData = this.getTaskData(this.draggedElement);
        const sourceId = this.sourceContainer.id;
        const targetId = dropTarget.id;
        
        // Move the task element
        if (dropTarget.classList.contains('sprinter-column')) {
            const tasksList = dropTarget.querySelector('.tasks-list');
            tasksList.appendChild(this.draggedElement);
            
            // Update task styling for assignment
            this.draggedElement.classList.remove('backlog-task');
            this.draggedElement.classList.add('assigned-task');
        } else if (dropTarget.classList.contains('backlog')) {
            dropTarget.appendChild(this.draggedElement);
            
            // Update task styling for backlog
            this.draggedElement.classList.remove('assigned-task');
            this.draggedElement.classList.add('backlog-task');
        }
        
        // Trigger drop event
        this.triggerEvent('taskMoved', {
            task: taskData,
            sourceContainer: sourceId,
            targetContainer: targetId
        });
        
        // Update capacity displays
        this.updateCapacityDisplays();
    }

    returnToSource() {
        // Add return animation
        this.draggedElement.style.transition = 'transform 0.3s ease';
        this.draggedElement.style.transform = 'translateX(0) translateY(0)';
        
        setTimeout(() => {
            this.draggedElement.style.transition = '';
            this.draggedElement.style.transform = '';
        }, 300);
    }

    cleanupDrag() {
        // Remove drag preview
        const preview = document.getElementById('drag-preview');
        if (preview) {
            preview.remove();
        }
        
        // Remove dragging class
        if (this.draggedElement) {
            this.draggedElement.classList.remove('dragging');
        }
        
        // Remove drop zone highlights
        document.querySelectorAll('.sprinter-column, .backlog').forEach(zone => {
            zone.classList.remove('drag-over');
        });
        
        // Reset cursor
        document.body.style.cursor = '';
    }

    highlightDropZones() {
        // Add subtle highlight to valid drop zones
        document.querySelectorAll('.sprinter-column, .backlog').forEach(zone => {
            if (zone !== this.sourceContainer) {
                zone.style.transition = 'all 0.2s ease';
            }
        });
    }

    getTaskData(taskElement) {
        return {
            id: taskElement.dataset.taskId,
            title: taskElement.querySelector('.task-title')?.textContent,
            sp: parseInt(taskElement.querySelector('.task-sp')?.textContent) || 0,
            priority: taskElement.dataset.priority || 'medium',
            description: taskElement.dataset.description || ''
        };
    }

    updateCapacityDisplays() {
        // This will be called from dashboard.js
        if (window.dashboardManager) {
            window.dashboardManager.updateCapacityDisplays();
        }
    }

    triggerEvent(eventName, data) {
        const event = new CustomEvent(eventName, { detail: data });
        document.dispatchEvent(event);
    }

    // Public methods for external use
    enableDragDrop() {
        document.querySelectorAll('.backlog-task, .assigned-task').forEach(task => {
            task.style.cursor = 'grab';
        });
    }

    disableDragDrop() {
        document.querySelectorAll('.backlog-task, .assigned-task').forEach(task => {
            task.style.cursor = 'default';
        });
    }
}

// Initialize drag and drop when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.sprintDragDrop = new SprintDragDrop();
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SprintDragDrop;
}