/* ═══════════════════════════════════
   Admin Panel JS
   ═══════════════════════════════════ */

document.addEventListener('DOMContentLoaded', function() {
    // Sidebar toggle
    const toggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('adminSidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', () => {
            sidebar.classList.toggle('show');
        });
    }

    // Auto-dismiss flash messages
    document.querySelectorAll('.flash-msg').forEach(msg => {
        setTimeout(() => {
            msg.style.opacity = '0';
            setTimeout(() => msg.remove(), 300);
        }, 5000);
    });

    // Close dropdown on outside click
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.action-dropdown')) {
            document.querySelectorAll('.dropdown-menu.show').forEach(m => m.classList.remove('show'));
        }
    });

    // Confirm destructive actions
    document.querySelectorAll('form').forEach(form => {
        const btn = form.querySelector('button');
        if (btn && (btn.textContent.includes('🗑️') || btn.textContent.includes('Ban') || btn.textContent.includes('⚡'))) {
            form.addEventListener('submit', function(e) {
                if (!confirm('Are you sure you want to perform this action?')) {
                    e.preventDefault();
                }
            });
        }
    });
});
