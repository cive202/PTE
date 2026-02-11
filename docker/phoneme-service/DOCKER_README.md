# Wav2Vec2 Phoneme Service Docker Instructions

## 1. Build the Docker Image
Run this command in the directory containing the Dockerfile:

```bash
docker build -t wav2vec2-service .
```

## 2. Transfer the Image to Another Machine

### Option A: Using a Tarball (No Registry Required)
This is useful if the target machine is offline or you don't want to use a Docker registry.

1.  **Save the image to a file:**
    ```bash
    docker save -o wav2vec2-service.tar wav2vec2-service
    ```
2.  **Transfer the file** (`wav2vec2-service.tar`) to the target machine (via USB, SCP, etc.).
3.  **Load the image on the target machine:**
    ```bash
    docker load -i wav2vec2-service.tar
    ```

### Option B: Using a Docker Registry (Docker Hub) - **Recommended for Ease of Use**
This is the easiest way to share the image between computers if both have internet access.

1.  **Create a Repository:**
    *   Go to [hub.docker.com](https://hub.docker.com) and sign up/log in.
    *   Click "Create Repository".
    *   Name it `wav2vec2-service`.
    *   **Note:** Free accounts make repositories *Public* by default. If your code is private, make sure to select *Private* (you usually get 1 free private repo).

2.  **Login in Terminal:**
    ```bash
    docker login
    ```
    (Enter your Docker Hub username and password/token)

3.  **Tag and Push:**
    Replace `your-username` with your actual Docker Hub username.
    ```bash
    # Tag the local image with your hub username
    docker tag wav2vec2-service your-username/wav2vec2-service:latest

    # Upload to Docker Hub
    docker push your-username/wav2vec2-service:latest
    ```

4.  **Pull on Target Machine:**
    ```bash
    docker pull your-username/wav2vec2-service:latest
    docker run -d -p 8001:8001 --name phoneme-service your-username/wav2vec2-service:latest
    ```

## 3. Run the Container
Run the service, mapping port 8001:

```bash
docker run -d -p 8001:8001 --name phoneme-service wav2vec2-service
```

## 4. Test the Service

**Health Check:**
```bash
curl http://localhost:8001/health
```

**Extract Phonemes:**
```bash
curl -X POST -F "audio=@/path/to/your/audio.wav" http://localhost:8001/phonemes
```
