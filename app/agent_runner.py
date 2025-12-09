from app.whatsapp_sender import WhatsAppSender

class AgentRunner:
    def __init__(self, sender: WhatsAppSender):
        self.sender = sender

    def start(self):
        self.sender.start()

    def ensure_login(self):
        return self.sender.ensure_login()

    def send_quiz_blast(self, contacts, template):
        return self.sender.send_bulk(contacts, template)

    def events(self):
        return self.sender.get_events()
