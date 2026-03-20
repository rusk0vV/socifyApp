import numpy as np
import joblib
import os

def predict_views(subscribers_input):
    # Get the directory where this file is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Load model and transformer with full paths
    model = joblib.load(os.path.join(current_dir, 'polunomial_model1.pkl'))
    poly = joblib.load(os.path.join(current_dir, 'poly_transformer1.pkl'))

    # Transform input
    log_input = np.log1p([[subscribers_input]])  # Shape: (1, 1)
    log_input_poly = poly.transform(log_input)

    # Predict
    log_predicted_views = model.predict(log_input_poly)
    predicted_views = np.expm1(log_predicted_views[0])  # Reverse log1p

    return predicted_views


# Only run the test if this file is executed directly, not when imported
if __name__ == "__main__":
    print(predict_views(29000000))  # Example usage
    # This will print the predicted views for a channel with 1000 subscribers.  