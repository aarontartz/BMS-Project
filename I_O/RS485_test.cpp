#include <iostream>
#include <fcntl.h>
#include <unistd.h>
#include <termios.h>
#include <wiringPi.h>  // For GPIO control

#define RS485_GPIO_CONTROL 18  // GPIO pin to control RS485 direction
#define SERIAL_PORT "/dev/serial0"

void configure_serial(int fd) {
    struct termios options;
    tcgetattr(fd, &options);
    
    // Set baud rate
    cfsetispeed(&options, B9600);
    cfsetospeed(&options, B9600);
    
    // 8N1 Mode: 8 Data bits, No Parity, 1 Stop bit
    options.c_cflag &= ~PARENB; // No parity
    options.c_cflag &= ~CSTOPB; // 1 stop bit
    options.c_cflag &= ~CSIZE;  
    options.c_cflag |= CS8; // 8 data bits
    
    // Set to raw mode (no processing)
    options.c_lflag &= ~(ICANON | ECHO | ECHOE | ISIG);
    options.c_iflag &= ~(IXON | IXOFF | IXANY); // Disable software flow control
    
    tcsetattr(fd, TCSANOW, &options);
}

void send_data(int fd, const std::string& data) {
    digitalWrite(RS485_GPIO_CONTROL, HIGH); // Enable transmission mode
    usleep(1000); // Small delay to settle

    write(fd, data.c_str(), data.length());
    usleep(1000); // Small delay to allow transmission

    digitalWrite(RS485_GPIO_CONTROL, LOW); // Set back to receive mode
}

std::string receive_data(int fd) {
    char buffer[256];
    int bytes_read = read(fd, buffer, sizeof(buffer) - 1);
    if (bytes_read > 0) {
        buffer[bytes_read] = '\0'; // Null-terminate string
        return std::string(buffer);
    }
    return "";
}

int main() {
    // Initialize GPIO for RS485 control
    wiringPiSetupGpio();
    pinMode(RS485_GPIO_CONTROL, OUTPUT);
    digitalWrite(RS485_GPIO_CONTROL, LOW); // Default to receiving mode

    // Open serial port
    int serial_fd = open(SERIAL_PORT, O_RDWR | O_NOCTTY | O_NDELAY);
    if (serial_fd == -1) {
        std::cerr << "Error opening serial port!" << std::endl;
        return 1;
    }

    // Configure serial port for RS485
    configure_serial(serial_fd);

    // Example: Send data
    send_data(serial_fd, "Hello RS485!\n");

    // Example: Receive data
    std::string received = receive_data(serial_fd);
    if (!received.empty()) {
        std::cout << "Received: " << received << std::endl;
    }

    // Close serial port
    close(serial_fd);
    return 0;
}
