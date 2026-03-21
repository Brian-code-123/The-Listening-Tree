/**
 * The Listening Tree - UI Component System (Vanilla JS)
 * This mimics a component-based structure (React/Ionic) to keep the app scalable
 * for the Capacitor environment.
 */

const UI = {
    /**
     * Create a Chat Message Bubble component
     */
    MessageBubble: (sender, content, time, isImage = false) => {
        const isBot = (sender === 'bot');
        const containerClass = isBot ? 'justify-content-start' : 'justify-content-end';
        const imgClass = isBot ? 'img_cont_msg' : 'img_cont_msg';
        const avatar = isBot ? '/static/Chatbot.png' : '/static/User.png';
        const msgContainerClass = isBot ? 'msg_container' : 'msg_container_send';
        const timeClass = isBot ? 'msg_time' : 'msg_time_send';

        let innerContent = isImage 
            ? `<img src="${content}" style="border-radius:10px; width:150px; height:auto; object-fit:cover;">`
            : content;

        return `
            <div class="d-flex ${containerClass} mb-4">
                ${isBot ? `<div class="${imgClass}"><img src="${avatar}" class="rounded-circle user_img_msg"></div>` : ''}
                <div class="${msgContainerClass}">
                    ${innerContent}
                    <span class="${timeClass}">${time}</span>
                </div>
                ${!isBot ? `<div class="${imgClass}"><img src="${avatar}" class="rounded-circle user_img_msg"></div>` : ''}
            </div>
        `;
    },

    /**
     * Create a Reminder Item component
     */
    ReminderItem: (item, translations) => {
        return `
            <div class="reminder-item ${item.is_active ? '' : 'expired'}" id="rem-${item.id}">
                <div class="reminder-info">
                    <span class="reminder-label">${item.label}</span>
                    <span class="reminder-time"><i class="far fa-clock"></i> ${item.reminder_time}</span>
                </div>
                <button class="delete-reminder" onclick="deleteReminder(${item.id})" title="${translations.delete || 'Delete'}">
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
                <a href="${article.link}" target="_blank" class="news-link">
                    <div class="news-title">${article.title}</div>
                    <div class="news-meta">
                        <span class="news-source"><i class="fas fa-bookmark"></i> ${article.source}</span>
                        <span class="news-date">${article.pubDate}</span>
                    </div>
                </a>
            </div>
        `;
    }
};

window.UI = UI;
