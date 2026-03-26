@echo off
echo ============================================================
echo 安装 PyTorch Nightly 版本以支持 RTX 5070
echo ============================================================
echo.

echo 步骤 1: 卸载当前 PyTorch
pip uninstall torch torchvision torchaudio -y

echo.
echo 步骤 2: 安装 PyTorch Nightly (支持最新 CUDA 架构)
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu124

echo.
echo 步骤 3: 验证安装
python -c "import torch; print('PyTorch 版本:', torch.__version__); print('CUDA 可用:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"

echo.
echo ============================================================
echo 安装完成！
echo ============================================================
pause
