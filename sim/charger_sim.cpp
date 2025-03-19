#include <iostream>
#include <string>
#include <chrono>
#include <thread>
#include <mqtt/async_client.h>

#define SERVER_ADDRESS "tcp://localhost:1883" // Change to your MQTT broker IP
#define CLIENT_ID "openevse_simulator"
#define BASE_TOPIC "openevse" // Base MQTT topic (update based on OpenEVSE settings)

using namespace std;
using namespace std::chrono;

// Callback class to handle messages received from OpenEVSE
class callback : public virtual mqtt::callback {
public:
    void message_arrived(mqtt::const_message_ptr msg) override {
        cout << "Received: " << msg->get_topic() << " -> " << msg->to_string() << endl;
    }
};

void send_command(mqtt::async_client& client, const string& topic, const string& payload) {
    cout << "Publishing: " << topic << " -> " << payload << endl;
    mqtt::message_ptr pubmsg = mqtt::make_message(topic, payload);
    client.publish(pubmsg);
}

int main() {
    // Create MQTT client
    mqtt::async_client client(SERVER_ADDRESS, CLIENT_ID);
    callback cb;
    client.set_callback(cb);

    // Connect to broker
    mqtt::connect_options connOpts;
    connOpts.set_clean_session(true);
    client.connect(connOpts)->wait();
    cout << "Connected to MQTT broker at " << SERVER_ADDRESS << endl;

    // Subscribe to OpenEVSE status topics
    client.subscribe(BASE_TOPIC "/status", 1);
    client.subscribe(BASE_TOPIC "/amp", 1);
    client.subscribe(BASE_TOPIC "/volt", 1);
    client.subscribe(BASE_TOPIC "/wh", 1);

    // Simulated commands
    this_thread::sleep_for(seconds(2));

    // 1. Start normal charging at 32A
    send_command(client, BASE_TOPIC "/rapi/in/$SC", "32");  // Set charge current to 32A
    send_command(client, BASE_TOPIC "/rapi/in/$FE", "");    // Start charging

    this_thread::sleep_for(seconds(5)); // Simulate time passing

    // 2. Enable V2G mode (Vehicle-to-Grid)
    send_command(client, BASE_TOPIC "/rapi/in/$V2G", "1");  // Enable V2G
    send_command(client, BASE_TOPIC "/rapi/in/$SC", "-20"); // Discharge at 20A (negative for export)

    this_thread::sleep_for(seconds(10)); // Simulate bidirectional power flow

    // 3. Stop charging / discharging
    send_command(client, BASE_TOPIC "/rapi/in/$FS", ""); // Stop charging/discharging

    // Disconnect
    client.disconnect()->wait();
    cout << "Disconnected from MQTT broker." << endl;

    return 0;
}
