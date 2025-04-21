// Упрощенный скрипт для переключения темы
document.addEventListener('DOMContentLoaded', function() {
    console.log('Theme switcher loaded');
    
    // Получаем кнопку переключения темы
    const themeToggleBtn = document.getElementById('theme-toggle');
    console.log('Theme toggle button:', themeToggleBtn);
    
    if (themeToggleBtn) {
        // Обработчик клика по кнопке
        themeToggleBtn.addEventListener('click', function() {
            console.log('Theme button clicked');
            
            // Получаем текущую тему
            const htmlElement = document.documentElement;
            const currentTheme = htmlElement.getAttribute('data-bs-theme');
            console.log('Current theme:', currentTheme);
            
            // Меняем тему
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            console.log('Switching to:', newTheme);
            
            // Устанавливаем новую тему
            htmlElement.setAttribute('data-bs-theme', newTheme);
            
            // Сохраняем в localStorage
            localStorage.setItem('theme', newTheme);
            
            // Меняем иконку
            const themeIcon = themeToggleBtn.querySelector('i');
            if (themeIcon) {
                if (newTheme === 'dark') {
                    themeIcon.className = 'fas fa-moon';
                } else {
                    themeIcon.className = 'fas fa-sun';
                }
            }
            
            // Добавляем дополнительную анимацию для видимого эффекта
            themeToggleBtn.classList.add('theme-toggled');
            setTimeout(function() {
                themeToggleBtn.classList.remove('theme-toggled');
            }, 500);
            
            alert('Тема изменена на: ' + (newTheme === 'dark' ? 'темную' : 'светлую'));
        });
    } else {
        console.error('Theme toggle button not found!');
    }
    
    // Проверяем сохраненную тему при загрузке
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-bs-theme', savedTheme);
        
        // Обновляем иконку
        if (themeToggleBtn) {
            const themeIcon = themeToggleBtn.querySelector('i');
            if (themeIcon) {
                if (savedTheme === 'dark') {
                    themeIcon.className = 'fas fa-moon';
                } else {
                    themeIcon.className = 'fas fa-sun';
                }
            }
        }
    }
});