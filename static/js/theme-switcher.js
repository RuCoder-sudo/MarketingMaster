// Скрипт для переключения темы (версия 2)
document.addEventListener('DOMContentLoaded', function() {
    console.log('Theme switcher v2 loaded');
    
    // Добавим атрибут data-bs-theme к HTML-элементу, если его нет
    const htmlElement = document.documentElement;
    if (!htmlElement.hasAttribute('data-bs-theme')) {
        htmlElement.setAttribute('data-bs-theme', 'light');
    }
    
    // Получаем кнопку переключения темы
    const themeToggleBtn = document.getElementById('theme-toggle');
    console.log('Theme toggle button found:', themeToggleBtn !== null);
    
    if (!themeToggleBtn) {
        console.error('Theme toggle button not found!');
        return; // Выходим из функции, если кнопка не найдена
    }
    
    // Функция для обновления иконки
    function updateIcon(theme) {
        const themeIcon = themeToggleBtn.querySelector('i');
        if (themeIcon) {
            if (theme === 'dark') {
                themeIcon.className = 'fas fa-moon';
            } else {
                themeIcon.className = 'fas fa-sun';
            }
        }
    }
    
    // Загрузка сохраненной темы из localStorage
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        htmlElement.setAttribute('data-bs-theme', savedTheme);
        updateIcon(savedTheme);
        console.log('Loaded saved theme:', savedTheme);
    }
    
    // Обработчик клика по кнопке переключения темы
    themeToggleBtn.addEventListener('click', function(event) {
        event.preventDefault(); // Предотвращаем стандартное поведение кнопки
        console.log('Theme button clicked');
        
        // Получаем текущую тему
        const currentTheme = htmlElement.getAttribute('data-bs-theme') || 'light';
        console.log('Current theme:', currentTheme);
        
        // Меняем тему
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        console.log('Switching to:', newTheme);
        
        // Устанавливаем новую тему
        htmlElement.setAttribute('data-bs-theme', newTheme);
        
        // Сохраняем в localStorage
        localStorage.setItem('theme', newTheme);
        
        // Обновляем иконку
        updateIcon(newTheme);
        
        // Добавляем анимацию
        themeToggleBtn.classList.add('theme-toggled');
        setTimeout(function() {
            themeToggleBtn.classList.remove('theme-toggled');
        }, 500);
        
        console.log('Theme switched successfully to:', newTheme);
    });
    
    // Принудительно устанавливаем начальное состояние стилей для темной/светлой темы
    function applyThemeStyles() {
        const currentTheme = htmlElement.getAttribute('data-bs-theme') || 'light';
        document.body.classList.remove('theme-dark', 'theme-light');
        document.body.classList.add('theme-' + currentTheme);
        
        // Применяем стили для Navbar и Footer в зависимости от темы
        const navbarElements = document.querySelectorAll('.navbar.bg-dark');
        const footerElements = document.querySelectorAll('footer.bg-dark');
        
        if (currentTheme === 'light') {
            navbarElements.forEach(el => {
                el.style.backgroundColor = '#f8f9fa';
                el.style.color = '#212529';
            });
            
            footerElements.forEach(el => {
                el.style.backgroundColor = '#f8f9fa';
                el.style.color = '#212529';
                el.style.borderTop = '1px solid #dee2e6';
            });
        } else {
            navbarElements.forEach(el => {
                el.style.backgroundColor = '';
                el.style.color = '';
            });
            
            footerElements.forEach(el => {
                el.style.backgroundColor = '';
                el.style.color = '';
                el.style.borderTop = '';
            });
        }
    }
    
    // Применяем стили при загрузке
    applyThemeStyles();
});