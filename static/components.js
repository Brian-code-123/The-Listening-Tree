/**
 * The Listening Tree - UI Component System (Vanilla JS)
 * This mimics a component-based structure (React/Ionic) to keep the app scalable
 * for the Capacitor environment.
 */

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

const UI = {
    /**
     * Create a Chat Message Bubble component
     */
    MessageBubble: (sender, content, time, isImage = false) => {
        const isBot = (sender === 'bot');
        const containerClass = isBot ? 'justify-content-start' : 'justify-content-end';
        const imgClass = 'img_cont_msg';
        const avatar = isBot ? '/static/Chatbot.png' : '/static/User.png';
        const msgContainerClass = isBot ? 'msg_cotainer' : 'msg_cotainer_send';
        const timeClass = 'msg_time';

        const innerContent = isImage
            ? `<img src="${escapeHtml(content)}" alt="Shared image" style="border-radius:10px; width:150px; height:auto; object-fit:cover;">`
            : escapeHtml(content);

        return `
            <div class="d-flex ${containerClass} mb-4 fade-in">
                ${isBot ? `<div class="${imgClass}"><img src="${avatar}" class="rounded-circle user_img_msg"></div>` : ''}
                <div class="${msgContainerClass}">
                    ${innerContent}
                    <span class="${timeClass}">${escapeHtml(time)}</span>
                </div>
                ${!isBot ? `<div class="${imgClass}"><img src="${avatar}" class="rounded-circle user_img_msg"></div>` : ''}
            </div>
        `;
    },

    /**
     * Create a Reminder Item component
     */
    ReminderItem: (item, translations) => {
        const deleteLabel = translations && translations.delete ? translations.delete : 'Delete';
        return `
            <div class="reminder-item ${item.is_active ? '' : 'expired'}" id="rem-${item.id}">
                <div class="reminder-info">
                    <span class="reminder-label">${escapeHtml(item.label)}</span>
                    <span class="reminder-time"><i class="far fa-clock"></i> ${escapeHtml(item.reminder_time)}</span>
                </div>
                <button class="delete-reminder" onclick="deleteReminder(${item.id})" title="${escapeHtml(deleteLabel)}">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
    },

    /**
     * Create a News Card component
     */
    NewsItem: (article) => {
        return `
            <div class="news-item">
                <a href="${escapeHtml(article.link)}" target="_blank" rel="noopener noreferrer" class="news-link">
                    <div class="news-title">${escapeHtml(article.title)}</div>
                    <div class="news-meta">
                        <span class="news-source"><i class="fas fa-bookmark"></i> ${escapeHtml(article.source)}</span>
                        <span class="news-date">${escapeHtml(article.pubDate)}</span>
                    </div>
                </a>
            </div>
        `;
    }
};

if (typeof window !== 'undefined') {
    window.UI = UI;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = UI;
}
