import sys
import os

# Add current directory to sys.path so we can import app
sys.path.append(os.getcwd())

from app.services.project_detection import ProjectDetectionService, ProjectType

def run_test():
    detector = ProjectDetectionService()
    
    # Force the path to be relative to where you are running the command
    current_dir = os.getcwd()
    base_path = os.path.join(current_dir, "tests", "data")
    
    monolith_path = os.path.join(base_path, "monolith")
    microservices_path = os.path.join(base_path, "microservices")

    print(f"--- DEBUG INFO ---")
    print(f"Current Directory: {current_dir}")
    print(f"Looking for Test Data at: {base_path}")
    
    # Check if the folder actually exists
    if not os.path.exists(monolith_path):
        print(f"\n❌ ERROR: The folder '{monolith_path}' does not exist.")
        print("Please run the 'mkdir' commands again inside the 'backend' folder.")
        return

    print(f"\n--- RUNNING PROJECT DETECTION TESTS ---")

    # TEST 1: MONOLITH
    print(f"Scanning: {monolith_path}")
    result_mono = detector.detect_project_type(monolith_path)
    print(f"Result: {result_mono}")
    
    if result_mono == ProjectType.MONOLITH:
        print("✅ PASS: Identified Monolith Correctly")
    else:
        print(f"❌ FAIL: Expected MONOLITH, got {result_mono}")
        print(f"   (Debug: Does '{monolith_path}/requirements.txt' exist?)")

    print("-" * 30)

    # TEST 2: MICROSERVICES
    print(f"Scanning: {microservices_path}")
    result_micro = detector.detect_project_type(microservices_path)
    print(f"Result: {result_micro}")

    if result_micro == ProjectType.MICROSERVICES:
        print("✅ PASS: Identified Microservices Correctly")
    else:
        print(f"❌ FAIL: Expected MICROSERVICES, got {result_micro}")
        print(f"   (Debug: Does '{microservices_path}/auth/requirements.txt' exist?)")

if __name__ == "__main__":
    run_test()