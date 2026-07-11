// File-based test: reads one SteakPacket from steak_pulse_test.bin.
// The live pipeline uses main.cpp + stdin (see README and steak_consumer).
#include <iostream>
#include <fstream>
#include "../include/SteakPacket.h"

int main() {
  SteakPacket packet;


  // Open the bin 
  std::ifstream input("/workspaces/steakTracker/perception/steak_pulse_test.bin", std::ios::binary);

  if (!input){
    std::cout << "Did you run the /perception/pulse_test.py?" << std::endl;
    return 1;
  }
  // Read the memory address of the struct that pulse_test.py placed in the steak_pulse_test.bin file...
  input.read(reinterpret_cast<char*> (&packet), sizeof(SteakPacket));


  if (input) {
    // output the read data
    std::cout << "--------- Steak Data Received ----------" << std::endl;
    std::cout << "ID: " << packet.steak_id << std::endl;
    std::cout << "Center Location x:  " << packet.centroid_x << std::endl;
    std::cout << "Center Location y: " << packet.centroid_y << std::endl;
    std::cout << "conf: " << packet.confidence << std::endl;
    std::cout << "timestamp: " << packet.timestamp << std::endl;
  } else {
    std::cerr << "Error. We only read " << input.gcount() << " bytes. Expected 20!" << std::endl;
  }

  input.close();
  return 0;
}