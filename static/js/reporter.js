/* Reporter Dashboard JS */
document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss flash
    document.querySelectorAll('.flash-msg').forEach(msg => {
        setTimeout(() => {
            msg.style.opacity = '0';
            setTimeout(() => msg.remove(), 300);
        }, 5000);
    });
});
