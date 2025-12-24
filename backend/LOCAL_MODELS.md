# Local AI Models Integration

This guide explains how to use local AI models with Cloud Visualizer Pro instead of cloud-based services (Azure OpenAI, OpenAI). Local models run entirely on your machine, providing:

- **Privacy**: No data sent to cloud services
- **Cost savings**: No API usage charges
- **Offline capability**: Works without internet connection
- **Low latency**: No network round-trips

## Supported Backends

### 1. Ollama (Recommended for most users)
- **Best for**: Local development, privacy-focused deployments
- **Pros**: Easy setup, wide model selection, good performance
- **Cons**: Requires separate daemon process, 4GB+ RAM recommended
- **Models**: Llama 2, Llama 3, Mistral, CodeLlama, Phi-3, and more

### 2. Microsoft Foundry Local (Preview)
- **Best for**: On-device AI, Windows integration
- **Pros**: Automatic model management, tight integration with Microsoft ecosystem
- **Cons**: Preview software, limited model selection
- **Models**: Qwen 2.5, Phi-3, other optimized small models

---

## Quick Start with Ollama

### Installation

#### Windows
1. Download from [ollama.com/download](https://ollama.com/download)
2. Run the installer
3. Ollama runs automatically as a system service

#### macOS
```bash
brew install ollama
```

#### Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Pull a Model

```bash
# Recommended: Llama 2 (7B parameters, good balance)
ollama pull llama2

# Alternative: Smaller/faster model
ollama pull phi3

# Alternative: Better quality, larger size
ollama pull llama3
```

### Configure Environment

Create or edit `backend/.env`:

```bash
# Enable Ollama
USE_OLLAMA=true
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# Disable cloud services (optional)
USE_OPENAI_FALLBACK=false
```

### Install Python Dependencies

```bash
cd backend
pip install httpx  # Required for Ollama HTTP API
```

### Start the Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

You should see in the logs:
```
INFO: LocalModelClient initialized: backend=ollama, model=llama2
INFO: Creating local model agent 'AzureArchitectAgent' with backend=ollama
```

### Test the Integration

Open the frontend and try a prompt like:
```
Design a simple web application with a database
```

The agent will use your local Ollama model to generate the architecture diagram.

---

## Quick Start with Microsoft Foundry Local

### Installation

1. Install Foundry Local:
   ```bash
   pip install foundry-local-sdk openai
   ```

2. The first run will automatically download the model to your device.

### Configure Environment

Create or edit `backend/.env`:

```bash
# Enable Foundry Local
USE_FOUNDRY_LOCAL=true
FOUNDRY_LOCAL_ALIAS=qwen2.5-0.5b

# Disable cloud services (optional)
USE_OPENAI_FALLBACK=false
```

### Start the Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

First startup will download the model (~500MB for qwen2.5-0.5b). You'll see:
```
INFO: LocalModelClient initialized: backend=foundry_local, model=qwen2.5-0.5b
INFO: Initializing Foundry Local with alias: qwen2.5-0.5b
```

Subsequent starts will reuse the cached model.

---

## Available Models

### Ollama Models

| Model | Size | RAM Required | Best For |
|-------|------|--------------|----------|
| `phi3` | 2.3GB | 4GB | Quick testing, resource-constrained systems |
| `llama2` | 3.8GB | 8GB | **Recommended** - Good balance of quality and performance |
| `mistral` | 4.1GB | 8GB | High-quality responses, good reasoning |
| `llama3` | 4.7GB | 8GB | Latest Llama model, excellent quality |
| `codellama` | 3.8GB | 8GB | Code generation and analysis |
| `llama2:13b` | 7.4GB | 16GB | Higher quality, slower |
| `mixtral:8x7b` | 26GB | 32GB | Best quality, requires powerful hardware |

Pull any model:
```bash
ollama pull <model-name>
```

List installed models:
```bash
ollama list
```

### Foundry Local Models

| Alias | Model | Size | Best For |
|-------|-------|------|----------|
| `qwen2.5-0.5b` | Qwen 2.5 0.5B | ~500MB | **Default** - Fast, minimal resource usage |
| `phi-3-mini` | Phi-3 Mini | ~2GB | Better quality, still lightweight |

---

## Performance Tuning

### Ollama Optimization

#### GPU Acceleration (NVIDIA)
Ollama automatically uses your GPU if CUDA is available. Check with:
```bash
ollama run llama2 "Hello"  # Watch logs for GPU detection
```

#### Model Parameters
Fine-tune generation in your code by passing kwargs to `run()`:
```python
response = await agent.run(prompt, 
    num_predict=2048,      # Max tokens to generate
    temperature=0.7,       # Creativity (0.0-1.0)
    top_p=0.9,            # Nucleus sampling
    top_k=40              # Top-k sampling
)
```

#### Concurrent Requests
Ollama handles multiple concurrent requests efficiently. No special configuration needed.

### Foundry Local Optimization

Foundry Local automatically optimizes for your hardware. Model selection happens at initialization based on device capabilities.

---

## Troubleshooting

### Ollama: "Connection refused"

**Problem**: Backend can't connect to Ollama daemon.

**Solution**:
1. Check if Ollama is running:
   ```bash
   # Windows
   Get-Process ollama
   
   # macOS/Linux
   pgrep ollama
   ```

2. Start Ollama manually:
   ```bash
   ollama serve
   ```

3. Verify the URL:
   ```bash
   curl http://localhost:11434/api/tags
   ```

### Ollama: "Model not found"

**Problem**: Model specified in `.env` isn't installed.

**Solution**:
```bash
ollama list              # Check installed models
ollama pull llama2       # Install missing model
```

Update `.env` to match installed model:
```bash
OLLAMA_MODEL=llama2
```

### Foundry Local: "Download failed"

**Problem**: Model download interrupted or failed.

**Solution**:
1. Check internet connection
2. Clear cache and retry:
   ```bash
   rm -rf ~/.foundry-local/cache/*
   ```
3. Try a smaller model:
   ```bash
   FOUNDRY_LOCAL_ALIAS=qwen2.5-0.5b
   ```

### Slow Response Times

**Problem**: Responses take too long.

**Solutions**:
1. **Use a smaller model**:
   - Ollama: Switch from `llama2` → `phi3`
   - Foundry Local: Use `qwen2.5-0.5b` (default)

2. **Check system resources**:
   ```bash
   # Monitor CPU/RAM usage during generation
   top    # or htop
   ```

3. **Enable GPU acceleration** (Ollama only):
   - Install CUDA toolkit for NVIDIA GPUs
   - Install ROCm for AMD GPUs
   - Restart Ollama service

4. **Reduce generation length**:
   ```python
   response = await agent.run(prompt, num_predict=1024)  # Shorter max length
   ```

### Diagram JSON Quality Issues

**Problem**: Local models generate incomplete or incorrect Diagram JSON.

**Solutions**:
1. **Use a larger model**:
   - Ollama: Upgrade to `llama3` or `mistral`
   - Foundry Local: Try `phi-3-mini`

2. **Check prompt engineering**:
   - Our prompts are optimized for GPT-4 class models
   - Smaller models may need simpler prompts or more examples

3. **Validate output**:
   - Check backend logs for JSON parsing errors
   - Frontend will show errors if diagram structure is invalid

---

## Production Deployment Considerations

### Security
- Local models run on your infrastructure → full data control
- No API keys to manage or rotate
- Network isolation possible (no outbound API calls)

### Scaling
- **Horizontal**: Deploy multiple backend instances, each with Ollama
- **Vertical**: Larger models require more RAM/GPU
- **Load balancing**: Ollama handles concurrent requests well

### Monitoring
- Monitor RAM/GPU usage per request
- Track response times (expect 5-30s for complex diagrams)
- Log model version for reproducibility

### Cost Analysis
| Deployment | Cost | Performance | Use Case |
|------------|------|-------------|----------|
| Azure OpenAI | $0.01-0.10/request | Excellent | Production, enterprise |
| Ollama (local server) | Hardware cost only | Good-Excellent | Privacy-focused, high volume |
| Foundry Local | Included with device | Good | Embedded, offline |

---

## Comparing Cloud vs Local

| Feature | Cloud (Azure/OpenAI) | Local (Ollama/Foundry) |
|---------|---------------------|------------------------|
| **Setup** | API key only | Install model (~4GB download) |
| **Cost** | Per-request ($) | Hardware cost + electricity |
| **Privacy** | Data sent to cloud | Data stays local ✓ |
| **Quality** | Excellent (GPT-4) | Good (Llama 2/3) |
| **Speed** | Fast (1-5s) | Medium (5-30s, depends on hardware) |
| **Offline** | ❌ Requires internet | ✓ Works offline |
| **Scaling** | Automatic | Manual (add hardware) |

---

## Advanced Configuration

### Custom Ollama Endpoint

If Ollama runs on a different machine:

```bash
# .env
USE_OLLAMA=true
OLLAMA_URL=http://192.168.1.100:11434
OLLAMA_MODEL=llama2
```

### Multiple Model Backends

You can switch backends by changing environment variables without code changes:

```bash
# Development: Use Ollama
USE_OLLAMA=true
USE_FOUNDRY_LOCAL=false

# Testing: Use Foundry Local
USE_OLLAMA=false
USE_FOUNDRY_LOCAL=true

# Production: Use Azure OpenAI
USE_OLLAMA=false
USE_FOUNDRY_LOCAL=false
USE_OPENAI_FALLBACK=false
# (Azure credentials via DefaultAzureCredential)
```

### Mixing Local and Cloud

For hybrid deployments (e.g., local for development, cloud for production), use environment-based configuration:

```python
# Different .env files for different environments
# .env.development
USE_OLLAMA=true

# .env.production
USE_OLLAMA=false
# Azure credentials via managed identity
```

---

## Next Steps

1. **Try different models**: Experiment with model selection for your use case
2. **Monitor performance**: Track response times and quality
3. **Optimize prompts**: Smaller models may benefit from prompt tuning
4. **Scale horizontally**: Add more backend instances as needed

For questions or issues, check:
- [Ollama Documentation](https://github.com/ollama/ollama)
- [Foundry Local Docs](https://learn.microsoft.com/azure/ai-studio/how-to/foundry-local)
- Project README and GitHub issues
