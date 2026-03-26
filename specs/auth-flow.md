# Auth Flow Specification

## Overview
User registration and login system with password security, session persistence, and email normalization.

## Functional Requirements

### 1. Registration (POST /register)
**Input:**
- `email` (string, required): user email
- `password` (string, required): user password

**Process:**
- Normalize email to lowercase
- Validate email format (must match RFC 5322 basic pattern)
- Validate password strength (min 8 chars)
- Check for duplicate email in users table
- Hash password using PBKDF2-HMAC-SHA256 (390,000 iterations)
- Store user in database with hashed password
- Set session cookie with user_id = email

**Output:**
- Success: HTTP 303 redirect to /chat
- Failure: HTTP 200 + render register.html with error message

**Error cases:**
- Email already exists → "Email already registered"
- Invalid email → "Invalid email format"
- Weak password → "Password must be at least 8 characters"

### 2. Login (POST /login)
**Input:**
- `email` (string, required): user email
- `password` (string, required): user password

**Process:**
- Normalize email to lowercase
- Query user by email
- Retrieve stored password hash
- Verify submitted password against hash
- If plaintext detected → transparently hash and update DB
- Set session cookie with user_id = email
- Initialize user state (chat_history, user_game_states)

**Output:**
- Success: HTTP 303 redirect to /chat
- Failure: HTTP 200 + render login.html with error message

**Error cases:**
- User not found → "Invalid email or password"
- Password mismatch → "Invalid email or password"
- DB error → "Server error, try again later"

### 3. Session Persistence
**Requirements:**
- Session cookie name: `lt_session`
- Session secret: random (server-side)
- Session timeout: browser close
- Store user_id in session
- Normalize email to lowercase for consistency

## Data Model

### users table
```sql
CREATE TABLE users (
  email TEXT PRIMARY KEY,
  password TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
)
```

### Password Hash Format
```
pbkdf2_sha256$<iterations>$<salt>$<digest>
Example: pbkdf2_sha256$390000$abcd1234$xyz789...
```

## Non-Functional Requirements
- Password hashing must use PBKDF2 (not plaintext)
- Email must be case-insensitive (normalized to lowercase)
- Session must be secure (HTTPOnly cookie)
- Legacy plaintext passwords must be migrated on login
- All user queries must normalize email to lowercase

## Testing Requirements
- Unit tests for password hashing/verification
- Integration tests for register and login flows
- Test duplicate email rejection
- Test password strength validation
- Test session persistence across requests
- Test email normalization (uppercase → lowercase)
