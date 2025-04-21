// Theme switcher script
document.addEventListener('DOMContentLoaded', function() {
    const themeToggleBtn = document.getElementById('theme-toggle');
    
    // Функция обновления иконки в зависимости от темы
    function updateThemeIcon(theme) {
        if (themeToggleBtn) {
            const themeIcon = themeToggleBtn.querySelector('i');
            if (themeIcon) {
                if (theme === 'dark') {
                    themeIcon.className = 'fas fa-moon';
                } else {
                    themeIcon.className = 'fas fa-sun';
                }
            }
        }
    }
    
    if (themeToggleBtn) {
        const htmlElement = document.documentElement;
        
        // Проверяем сохраненную тему из localStorage
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) {
            htmlElement.setAttribute('data-bs-theme', savedTheme);
            updateThemeIcon(savedTheme);
        } else {
            // Если тема не сохранена, устанавливаем тему по умолчанию
            htmlElement.setAttribute('data-bs-theme', 'light');
            localStorage.setItem('theme', 'light');
            updateThemeIcon('light');
        }
        
        // Обработчик клика по кнопке переключения темы
        themeToggleBtn.addEventListener('click', function() {
            const currentTheme = htmlElement.getAttribute('data-bs-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            // Установка новой темы
            htmlElement.setAttribute('data-bs-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            
            // Обновление иконки
            updateThemeIcon(newTheme);
            
            console.log('Theme switched to:', newTheme);
        });
    }
});