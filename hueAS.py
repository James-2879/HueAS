
import pyaudio
from hue_api import HueApi # this is NOT the same API used in other scripts
import numpy as np
import time
from random import randint

LOW_BRI = 0
MID_BRI = 120
MAX_BRI = 254
# MAX_HUE = 65534

chunk = 1024  # 2**10
rate = 44100
fft_selection_filter = 12
hue_cycle_speed = 500
activation_threshold = 340000 
mid_act_thresh = 60000
run_time = 100000000 # in sec, infinite for now
normal_duration = 10 # need a smoothing thing for this

### TODO ###

# - FTT values should probably logged so choosing a threshold is more linear
# - Thresholds need to be normalized over a given cycle period in seconds proportional to track FTT values -> Proposed thresholds currently are not accurate
# - Make palette combinations
# - Make threshold intensity presets (low, medium, high, intense)
# - Initial brightness, hue, and bulb state should be recorded so they can be switched back after
# - Let each light choose a hue from the palatte individually

######################

if __name__ == "__main__":  
    
    api = HueApi()
    colors = ["red", "blue", "green", "orange", "pink", "purple"] # use simple color names
    # colors = [[21, 234, 45], [123, 2, 150]] # or parse RGB values as separate arrays
    # colors = [[255, 255, 255]]
    
    try:
        api.load_existing()
    except BaseException:
        pass
        input("Press the pairing button the Hue bridge, then press 'Enter' to continue...")
        bridge_address = "192.168.0.46"
        api.create_new_user(bridge_address)
        api.print_debug_info()
        api.save_api_key()
        print("")
    finally:
        # this should be in a try too
        api.fetch_lights()
        api.list_lights()
    
    p=pyaudio.PyAudio()
    # print devices so input_device_input_index can be selected below
    for i in range(p.get_device_count()):
        print(p.get_device_info_by_index(i))
    # open the stream, can be loopback, input, or output
    stream=p.open(format=pyaudio.paInt16,channels=1,rate=48000,input=True, #RATE
                frames_per_buffer=chunk, input_device_index=18)

    previous_bri = LOW_BRI
    ftt_values = []
    last_time = time.time()
    median = 0
    max = 0
    color = 0
    print("\nEND OF PREAMBLE\n")
    
    for i_data_blocks in range(int(run_time*rate/chunk)):
    
        current_time = time.time()
        if current_time - last_time >= 3:
            # there needs to be a 1 sec average and a 5 second average, and the 1sa causes adjsutments
            # maybe the faster moving average just adjust the mid brightness
            ## or the mid brightness threshold is moved closer to the median to increase dynamicness
            last_time = current_time
            median = np.median(ftt_values)
            max = np.max(ftt_values)
            proposed_activation_threshold = int(median * 1/3)
            proposed_mid_act_thresh = int(proposed_activation_threshold * 2/3)
            if proposed_activation_threshold < 5000:
                activation_threshold = 5000 # default -> set at top
                mid_act_thresh = 2500
            else:
                activation_threshold = proposed_activation_threshold
                mid_act_thresh = proposed_mid_act_thresh
            # print("median is:", median)
            # print("max is: ", max)
            ftt_values = []
        
            # need to incorporate a lower limit in this for when music stops
            
        data = np.fromstring(stream.read(chunk),dtype=np.int16)
        fft = np.fft.fft(data)
        # hue = str((i_data_blocks*hue_cycle_speed)%MAX_HUE) # this will cycle through colors indiscrimininatly
        bri = int(np.absolute(np.average(fft[0:fft_selection_filter])))
        ftt_values.append(bri)
        if bri < mid_act_thresh:
            bri = LOW_BRI
        elif bri > mid_act_thresh and bri < activation_threshold:
            bri = MID_BRI
        elif bri > activation_threshold:
            bri = MAX_BRI
        if bri != previous_bri:
            # control the lights here
            if bri == MAX_BRI:
                color = randint(0, len(colors) - 1)
                # print("Palette array index:", color)
                api.set_brightness(255, indices = [15, 16, 17])
                api.turn_on(indices = [15, 16, 17])
                api.set_color(colors[color], indices = [15, 16, 17])
                print("FTT_med:", median, "FTT_max:", max, "palette_index:", color, "#################### MAX ####################", end = "\r")
            elif bri == MID_BRI:
                api.set_brightness(215, indices = [15, 16, 17])
                api.turn_on(indices = [15, 16, 17])
                print("FTT_med:", median, "FTT_max:", max, "palette_index:", color, "-------------------- MED --------------------", end = "\r")
            elif bri == LOW_BRI:
                api.turn_off(indices = [15, 16, 17])
                print("FTT_med:", median, "FTT_max:", max, "palette_index:", color, "____________________ MIN ____________________", end = "\r")
        previous_bri = bri
    stream.stop_stream()
    stream.close()
    p.terminate()
