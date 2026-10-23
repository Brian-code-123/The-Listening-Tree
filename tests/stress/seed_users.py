"""Create N throwaway users in the local e2e database and print their emails as JSON."""
import json
import sys
import uuid

from tests.integration.helpers import create_user_direct

n = int(sys.argv[1])
run = uuid.uuid4().hex[:6]
emails = [f"load{run}_{i}@example.com" for i in range(n)]
for email in emails:
    create_user_direct(email)
print(json.dumps(emails))
