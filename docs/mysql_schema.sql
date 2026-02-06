-- Mail_Check MySQL schema (utf8mb4)
-- Usage (example):
--   1) Create database (optional): CREATE DATABASE IF NOT EXISTS `mail_check` DEFAULT CHARACTER SET utf8mb4;
--   2) USE `mail_check`;
--   3) Run this file.

CREATE TABLE IF NOT EXISTS processed_emails (
  id BIGINT NOT NULL AUTO_INCREMENT,
  token VARCHAR(255) UNIQUE,
  hospital_name VARCHAR(255),
  email_date VARCHAR(255),
  processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS event_groups (
  id BIGINT NOT NULL AUTO_INCREMENT,
  hospital_name VARCHAR(255),
  fingerprint BIGINT UNSIGNED,
  event_url VARCHAR(1024),
  total_count BIGINT DEFAULT 1,
  last_title TEXT,
  last_reason TEXT,
  last_source VARCHAR(255),
  last_sentiment_id VARCHAR(255),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS negative_sentiments (
  id BIGINT NOT NULL AUTO_INCREMENT,
  sentiment_id VARCHAR(255),
  event_id BIGINT,
  hospital_name VARCHAR(255),
  title TEXT,
  source VARCHAR(255),
  content LONGTEXT,
  reason TEXT,
  severity VARCHAR(20),
  url TEXT,
  status VARCHAR(20) DEFAULT 'active',
  is_duplicate TINYINT(1) DEFAULT 0,
  dismissed_at DATETIME,
  insight_text LONGTEXT,
  insight_at DATETIME,
  processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sentiment_feedback (
  id BIGINT NOT NULL AUTO_INCREMENT,
  sentiment_id VARCHAR(255),
  feedback_judgment TINYINT(1),
  feedback_type VARCHAR(50),
  feedback_text TEXT,
  user_id VARCHAR(255),
  feedback_time DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS feedback_queue (
  id BIGINT NOT NULL AUTO_INCREMENT,
  sentiment_id VARCHAR(255),
  user_id VARCHAR(255),
  sent_time DATETIME,
  status VARCHAR(20) DEFAULT 'pending',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS feedback_rules (
  id BIGINT NOT NULL AUTO_INCREMENT,
  pattern TEXT,
  rule_type VARCHAR(20),
  action VARCHAR(20),
  confidence DOUBLE,
  enabled TINYINT(1) DEFAULT 1,
  source_feedback_id BIGINT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Indexes
CREATE INDEX idx_negative_sentiments_processed_at ON negative_sentiments(processed_at);
CREATE INDEX idx_negative_sentiments_status ON negative_sentiments(status);
CREATE INDEX idx_negative_sentiments_hospital ON negative_sentiments(hospital_name);
CREATE INDEX idx_negative_sentiments_sentiment_id ON negative_sentiments(sentiment_id);
CREATE INDEX idx_negative_sentiments_event_id ON negative_sentiments(event_id);
CREATE INDEX idx_feedback_queue_user_status ON feedback_queue(user_id, status, sent_time);
CREATE INDEX idx_event_groups_hospital_time ON event_groups(hospital_name, last_seen_at);
CREATE INDEX idx_event_groups_fingerprint ON event_groups(fingerprint);
-- Prefix index avoids InnoDB key-length limit when event_url is long under utf8mb4
CREATE INDEX idx_event_groups_url ON event_groups(event_url(191));

