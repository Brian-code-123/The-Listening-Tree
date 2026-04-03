/**
 * Mermaid sequence diagram:
 * sequenceDiagram
 *     participant Test
 *     participant UI
 *     participant HTML
 *     Test->>UI: build message bubble / reminder / news item
 *     UI-->>Test: HTML string output
 */

const UI = require('../../static/components.js');

describe('UI component builders', () => {
  it('builds a bot message bubble', () => {
    const html = UI.MessageBubble('bot', 'Hello there', '09:15');

    expect(html).toContain('justify-content-start');
    expect(html).toContain('/static/Chatbot.png');
    expect(html).toContain('Hello there');
    expect(html).toContain('09:15');
  });

  it('builds a reminder item with delete action', () => {
    const html = UI.ReminderItem(
      { id: 7, label: 'Take medicine', reminder_time: '09:00', is_active: true },
      { delete: 'Delete' }
    );

    expect(html).toContain('rem-7');
    expect(html).toContain('Take medicine');
    expect(html).toContain('09:00');
    expect(html).toContain('deleteReminder(7)');
  });

  it('builds a news item link', () => {
    const html = UI.NewsItem({
      link: 'https://example.com/news',
      title: 'Sample news item',
      source: 'Example News',
      pubDate: '2026-04-03',
    });

    expect(html).toContain('https://example.com/news');
    expect(html).toContain('Sample news item');
    expect(html).toContain('Example News');
  });
});