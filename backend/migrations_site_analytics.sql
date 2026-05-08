-- Table dédiée analytics site / landing (sans lien avec card_visits / card_events)
-- À appliquer si create_all n’est pas utilisé (ex. prod SQLite existante).

CREATE TABLE IF NOT EXISTS site_analytics_events (
  id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  domain VARCHAR(255) NOT NULL,
  path VARCHAR(1024) NOT NULL,
  page_type VARCHAR(64) NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  source VARCHAR(255),
  referrer VARCHAR(512),
  utm_source VARCHAR(255),
  utm_medium VARCHAR(255),
  utm_campaign VARCHAR(255),
  lang VARCHAR(16),
  target VARCHAR(512),
  visitor_id VARCHAR(80),
  user_agent VARCHAR(256),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_site_analytics_events_domain ON site_analytics_events (domain);
CREATE INDEX IF NOT EXISTS ix_site_analytics_events_page_type ON site_analytics_events (page_type);
CREATE INDEX IF NOT EXISTS ix_site_analytics_events_event_type ON site_analytics_events (event_type);
CREATE INDEX IF NOT EXISTS ix_site_analytics_events_lang ON site_analytics_events (lang);
CREATE INDEX IF NOT EXISTS ix_site_analytics_events_visitor_id ON site_analytics_events (visitor_id);
CREATE INDEX IF NOT EXISTS ix_site_analytics_events_created_at ON site_analytics_events (created_at);
