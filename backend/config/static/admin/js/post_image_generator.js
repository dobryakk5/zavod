/**
 * JavaScript для генерации изображений постов в Django Admin
 */

(function() {
    'use strict';

    // Ждём загрузки DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initImageGenerator);
    } else {
        initImageGenerator();
    }

    function initImageGenerator() {
        const button = document.getElementById('generate-image-btn');
        if (!button) return;

        button.addEventListener('click', function(e) {
            e.preventDefault();

            const generateUrl = button.getAttribute('data-url');
            const statusDiv = document.getElementById('generate-status');

            // Отключить кнопку на время генерации
            button.disabled = true;
            button.textContent = 'Генерируется...';
            button.style.backgroundColor = '#6c757d';

            // Показать статус
            statusDiv.innerHTML = '<span style="color: #007bff;">⏳ Генерация изображения началась...</span>';

            // Получить CSRF токен
            const csrftoken = getCookie('csrftoken');

            // Отправить POST запрос
            fetch(generateUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.error || 'Ошибка генерации');
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    statusDiv.innerHTML = '<span style="color: #28a745;">✓ ' + data.message + '</span>';

                    // Автоматически перезагрузить страницу через 3 секунды
                    setTimeout(function() {
                        location.reload();
                    }, 3000);
                } else {
                    throw new Error(data.error || 'Неизвестная ошибка');
                }
            })
            .catch(error => {
                console.error('Ошибка:', error);
                statusDiv.innerHTML = '<span style="color: #dc3545;">✗ Ошибка: ' + error.message + '</span>';

                // Включить кнопку обратно при ошибке
                button.disabled = false;
                button.textContent = 'Сгенерировать изображение';
                button.style.backgroundColor = '#417690';
            });
        });
    }

    // Функция для получения CSRF токена из cookies
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
})();
