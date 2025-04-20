// Main JavaScript file for Social Media Monitoring application

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Initialize DataTables if present
    if (typeof $.fn.DataTable !== 'undefined' && document.querySelector('.datatable')) {
        $('.datatable').DataTable({
            language: {
                search: "Поиск:",
                lengthMenu: "Показать _MENU_ записей",
                info: "Отображено с _START_ по _END_ из _TOTAL_ записей",
                infoEmpty: "Записи отсутствуют",
                infoFiltered: "(отфильтровано из _MAX_ записей)",
                paginate: {
                    first: "Первая",
                    previous: "Предыдущая",
                    next: "Следующая",
                    last: "Последняя"
                }
            }
        });
    }
    
    // Color picker for keywords
    const colorInputs = document.querySelectorAll('.color-picker');
    colorInputs.forEach(input => {
        if (input) {
            // Preview color as background of parent element
            input.addEventListener('input', function() {
                const previewEl = this.closest('.input-group').querySelector('.color-preview');
                if (previewEl) {
                    previewEl.style.backgroundColor = this.value;
                }
            });
            
            // Set initial color
            const previewEl = input.closest('.input-group').querySelector('.color-preview');
            if (previewEl) {
                previewEl.style.backgroundColor = input.value;
            }
        }
    });
    
    // Handle API token visibility toggle
    const toggleButtons = document.querySelectorAll('.toggle-password');
    toggleButtons.forEach(button => {
        if (button) {
            button.addEventListener('click', function() {
                const input = document.getElementById(this.getAttribute('data-target'));
                if (input) {
                    if (input.type === 'password') {
                        input.type = 'text';
                        this.innerHTML = '<i class="fa fa-eye-slash"></i>';
                    } else {
                        input.type = 'password';
                        this.innerHTML = '<i class="fa fa-eye"></i>';
                    }
                }
            });
        }
    });
    
    // Confirm deletion actions
    const confirmDeleteButtons = document.querySelectorAll('[data-confirm]');
    confirmDeleteButtons.forEach(button => {
        if (button) {
            button.addEventListener('click', function(e) {
                if (!confirm(this.getAttribute('data-confirm'))) {
                    e.preventDefault();
                    return false;
                }
            });
        }
    });
    
    // Handle filter form submission
    const filterForm = document.getElementById('filter-form');
    if (filterForm) {
        const filterInputs = filterForm.querySelectorAll('input, select');
        filterInputs.forEach(input => {
            input.addEventListener('change', function() {
                filterForm.submit();
            });
        });
    }
    
    // Handle background search status updates
    function updateSearchStatus() {
        const statusElement = document.getElementById('search-status');
        if (statusElement) {
            fetch('/search/status')
                .then(response => response.json())
                .then(data => {
                    if (data.running) {
                        statusElement.innerHTML = '<span class="badge bg-success">Running</span>';
                        document.getElementById('start-search-btn').style.display = 'none';
                        document.getElementById('stop-search-btn').style.display = 'inline-block';
                    } else {
                        statusElement.innerHTML = '<span class="badge bg-secondary">Stopped</span>';
                        document.getElementById('start-search-btn').style.display = 'inline-block';
                        document.getElementById('stop-search-btn').style.display = 'none';
                    }
                })
                .catch(error => console.error('Error fetching search status:', error));
        }
    }
    
    // Periodically update search status if on search page
    if (document.getElementById('search-status')) {
        updateSearchStatus();
        setInterval(updateSearchStatus, 10000); // Update every 10 seconds
    }
    
    // Project rename functionality
    const renameButtons = document.querySelectorAll('.rename-project-btn');
    renameButtons.forEach(button => {
        if (button) {
            button.addEventListener('click', function() {
                const projectId = this.getAttribute('data-project-id');
                const projectName = this.getAttribute('data-project-name');
                
                const modal = document.getElementById('renameProjectModal');
                if (modal) {
                    const modalInstance = new bootstrap.Modal(modal);
                    document.getElementById('project_id').value = projectId;
                    document.getElementById('new_name').value = projectName;
                    modalInstance.show();
                }
            });
        }
    });
});
