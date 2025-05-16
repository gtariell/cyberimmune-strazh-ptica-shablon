# Кибериммунная система дрона "Страж-птица" v3.0
# Реализация с использованием MILS/FLASK, контейнеризации и RabbitMQ

import pika
import json
import logging
from threading import Thread
from time import sleep
import docker

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Конфигурация RabbitMQ
RABBITMQ_HOST = 'rabbitmq'
EXCHANGE_NAME = 'security_events'
POLICY_QUEUE = 'policy_check'

# Инициализация Docker клиента
docker_client = docker.from_env()

# Политики безопасности (пример)
SECURITY_POLICIES = {
    'flight_control': {
        'allowed_actions': ['position_update', 'emergency_stop'],
        'allowed_destinations': ['air_traffic', 'monitor']
    },
    'threat_detection': {
        'allowed_actions': ['threat_alert'],
        'allowed_destinations': ['defense_system']
    }
}

class MILSMonitor:
    """Реализация монитора безопасности по FLASK архитектуре"""
    def __init__(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST))
        self.channel = self.connection.channel()
        
        # Настройка обмена сообщениями
        self.channel.exchange_declare(
            exchange=EXCHANGE_NAME, 
            exchange_type='direct'
        )
        self.channel.queue_declare(queue=POLICY_QUEUE)
        
    def check_policy(self, message):
        """Проверка сообщения на соответствие политикам"""
        try:
            source = message['source']
            action = message['action']
            dest = message['destination']
            
            policy = SECURITY_POLICIES.get(source, {})
            if (action in policy.get('allowed_actions', []) and
                dest in policy.get('allowed_destinations', [])):
                return True
            return False
        except KeyError:
            return False

    def start_monitoring(self):
        """Запуск обработки сообщений"""
        def callback(ch, method, properties, body):
            message = json.loads(body)
            if self.check_policy(message):
                logging.info(f"APPROVED: {message}")
                # Перенаправление адресату
                self.channel.basic_publish(
                    exchange=EXCHANGE_NAME,
                    routing_key=message['destination'],
                    body=body
                )
            else:
                logging.warning(f"DENIED: {message}")

        self.channel.basic_consume(
            queue=POLICY_QUEUE,
            on_message_callback=callback,
            auto_ack=True
        )
        self.channel.start_consuming()

class SecurityComponent(Thread):
    """Базовый класс для компонентов системы"""
    def __init__(self, name):
        super().__init__(daemon=True)
        self.name = name
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST))
        self.channel = self.connection.channel()
        
    def send_message(self, destination, action, data):
        """Отправка сообщения через брокер"""
        message = {
            'source': self.name,
            'destination': destination,
            'action': action,
            'data': data
        }
        self.channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=POLICY_QUEUE,
            body=json.dumps(message)
        )

class FlightControl(SecurityComponent):
    """Система управления полетами"""
    def run(self):
        while True:
            self.send_message(
                destination='air_traffic',
                action='position_update',
                data={'coordinates': [55.7558, 37.6176]}
            )
            sleep(3)

class ThreatDetection(SecurityComponent):
    """Система обнаружения угроз"""
    def run(self):
        while True:
            self.send_message(
                destination='defense_system',
                action='threat_alert',
                data={'threat_id': 'T-001', 'level': 'high'}
            )
            sleep(5)

def setup_infrastructure():
    """Развертывание инфраструктуры с использованием Docker"""
    try:
        # Запуск RabbitMQ
        docker_client.containers.run(
            'rabbitmq:management',
            name='rabbitmq',
            ports={'5672/tcp': 5672, '15672/tcp': 15672},
            detach=True
        )
        
        # Создание сети для компонентов
        network = docker_client.networks.create('mils_network')
        network.connect('rabbitmq')
        
    except docker.errors.APIError as e:
        logging.error(f"Docker error: {e}")

if __name__ == "__main__":
    # Инициализация инфраструктуры
    setup_infrastructure()
    sleep(10)  # Ожидание инициализации RabbitMQ
    
    # Запуск компонентов
    monitor = MILSMonitor()
    flight = FlightControl('flight_control')
    threat = ThreatDetection('threat_detection')
    
    Thread(target=monitor.start_monitoring).start()
    flight.start()
    threat.start()
    
    # Демонстрация работы
    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        logging.info("Завершение работы системы")