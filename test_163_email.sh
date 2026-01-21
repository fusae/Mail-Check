#!/bin/bash

echo "=================================="
echo "   Testing 163 Email Connection"
echo "=================================="
echo ""

cd "$(dirname "$0")"
source venv/bin/activate

python3 << 'PYTEST'
import yaml
import imaplib

# Read config
with open('config/config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

email_config = config['email']
server = email_config['imap_server']
port = email_config.get('imap_port', 993)
email = email_config['email_address']
password = email_config['app_password']

print(f"Server: {server}:{port}")
print(f"Email: {email}")
print("")

try:
    # Connect to 163 IMAP
    mail = imaplib.IMAP4_SSL(server, port)
    mail.login(email, password)
    status, data = mail.select('INBOX')
    print("SELECT INBOX status:", status)
    print("SELECT INBOX data:", data)
    if status != 'OK':
        status, data = mail.select('INBOX', readonly=True)
        print("SELECT INBOX readonly status:", status)
        print("SELECT INBOX readonly data:", data)
    if status != 'OK':
        status, mailboxes = mail.list()
        print("LIST status:", status)
        if mailboxes:
            print("LIST mailboxes:")
            for line in mailboxes[:20]:
                print(" ", line.decode(errors='ignore'))
        if status == 'OK' and mailboxes:
            inbox = None
            for line in mailboxes:
                name = line.decode(errors='ignore')
                if 'INBOX' in name.upper():
                    inbox = name.split(' "/" ')[-1].strip('"')
                    break
            if inbox:
                print("Selecting mailbox:", inbox)
                status, data = mail.select(inbox)
    print("SELECT status:", status)
    print("SELECT data:", data)
    if status != 'OK':
        raise RuntimeError("无法选择邮件文件夹，服务器未进入SELECTED状态")
    
    print("SUCCESS: 163 email connected!")
    print(f"  Logged in: {email}")
    
    # Search for emails
    search_criteria = f'(FROM "sydc@yj.microvivid.com")'
    status, messages = mail.search(None, 'UNSEEN', search_criteria)
    
    if status == 'OK':
        count = len(messages[0].split()) if messages[0] else 0
        print(f"  Found {count} unread sentiment emails")
    else:
        print("  No emails found")
    
    mail.close()
    mail.logout()
    
except Exception as e:
    print(f"\nERROR: Connection failed")
    print(f"  {e}")
    print("\nPlease check:")
    print("  1. Email address is correct")
    print("  2. Authorization code is correct")
    print("  3. IMAP service is enabled")
    print("  4. Network connection is normal")
PYTEST

echo ""
echo "=================================="
echo "   Test Complete"
echo "=================================="
