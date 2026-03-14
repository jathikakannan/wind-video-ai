import time

def measure_inference(model_function, input_data):

    start = time.time()

    output = model_function(input_data)

    end = time.time()

    inference_time = end - start

    return output, inference_time