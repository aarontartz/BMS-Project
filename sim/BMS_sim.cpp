#include <iostream>
#include <string>
#include <mqtt/async_client.h>

#define SERVER_ADDRESS "tcp://localhost:1883"
#define CLIENT_ID "openevse_charger"
#define BASE_TOPIC "openevse"

using namespace std;

// Callback to process incoming messages (commands from Pi)
class callback : public virtual mqtt::callback {
public:
    mqtt::async_client& client;

    callback(mqtt::async_client& cli) : client(cli) {}

    void message_arrived(mqtt::const_message_ptr msg) override {
        string topic = msg->get_topic();
        string payload = msg->to_string();
        cout << "Charger received: " << topic << " -> " << payload << endl;

        // Simulate charger responses
        if (topic == BASE_TOPIC "/rapi/in/$SC") {
            client.publish(BASE_TOPIC "/status", "Charging current set");
        } else if (topic == BASE_TOPIC "/rapi/in/$FE") {
            client.publish(BASE_TOPIC "/status", "Charging started");
        } else if (topic == BASE_TOPIC "/rapi/in/$V2G") {
            client.publish(BASE_TOPIC "/status", "V2G mode enabled");
        } else if (topic == BASE_TOPIC "/rapi/in/$FS") {
            client.publish(BASE_TOPIC "/status", "Charging stopped");
        }
    }
};

int main() {
    mqtt::async_client client(SERVER_ADDRESS, CLIENT_ID);
    callback cb(client);
    client.set_callback(cb);

    mqtt::connect_options connOpts;
    connOpts.set_clean_session(true);
    client.connect(connOpts)->wait();
    cout << "Charger simulator connected to MQTT broker." << endl;

    // Subscribe to charger control commands
    client.subscribe(BASE_TOPIC "/rapi/in/#", 1);

    while (true) {
        // Simulated charger status update every 5 seconds
        client.publish(BASE_TOPIC "/status", "Charger is idle");
        this_thread::sleep_for(chrono::seconds(5));
    }

    client.disconnect()->wait();
    return 0;
}
