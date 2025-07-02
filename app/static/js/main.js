document.addEventListener('DOMContentLoaded', function() {
    // Инициализация модального окна для отправки email
    const emailModal = document.getElementById('emailModal');
    if (emailModal) {
        emailModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const supplierId = button.getAttribute('data-supplier-id');
            const modalInput = emailModal.querySelector('#supplierId');
            modalInput.value = supplierId;
        });
    }

    // Обработка отправки email
    const sendEmailBtn = document.getElementById('sendEmailBtn');
    if (sendEmailBtn) {
        sendEmailBtn.addEventListener('click', async function() {
            const form = document.getElementById('sendEmailForm');
            const formData = new FormData(form);
            const supplierId = formData.get('supplier_id');
            const templateId = formData.get('template_id');
            const senderEmail = formData.get('sender_email');

            try {
                const response = await fetch(`/send_email/${supplierId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: new URLSearchParams({
                        template_id: templateId,
                        sender_email: senderEmail
                    })
                });

                if (response.ok) {
                    alert('Email sent successfully');
                    const modal = bootstrap.Modal.getInstance(emailModal);
                    modal.hide();
                    // Можно обновить таблицу или добавить визуальное подтверждение
                } else {
                    const error = await response.text();
                    alert(`Error: ${error}`);
                }
            } catch (error) {
                alert(`Error: ${error.message}`);
            }
        });
    }

    // HTMX конфигурация
    document.body.addEventListener('htmx:configRequest', function(evt) {
        const token = getCookie('access_token');
        if (token) {
            evt.detail.headers['Authorization'] = token;
        }
    });
});

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}