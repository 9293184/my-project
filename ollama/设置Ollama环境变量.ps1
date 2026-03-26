# 设置 Ollama 模型存储位置到 D 盘
# 运行此脚本后需要重启 Ollama 服务

# 创建模型存储目录
$modelPath = "D:\ollama_models"
New-Item -ItemType Directory -Path $modelPath -Force | Out-Null

# 设置用户环境变量
[System.Environment]::SetEnvironmentVariable('OLLAMA_MODELS', $modelPath, 'User')

Write-Host "✅ 已设置 OLLAMA_MODELS 环境变量为: $modelPath" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  重要：需要重启 Ollama 服务才能生效" -ForegroundColor Yellow
Write-Host ""
Write-Host "请执行以下命令重启 Ollama：" -ForegroundColor Cyan
Write-Host "1. 关闭 Ollama（右键托盘图标 -> Quit）" -ForegroundColor White
Write-Host "2. 重新启动 Ollama" -ForegroundColor White
Write-Host ""
Write-Host "或者运行：" -ForegroundColor Cyan
Write-Host "  Stop-Process -Name ollama -Force" -ForegroundColor White
Write-Host "  Start-Process ollama" -ForegroundColor White
Write-Host ""

# 显示当前环境变量
Write-Host "当前环境变量设置：" -ForegroundColor Green
Write-Host "OLLAMA_MODELS = $([System.Environment]::GetEnvironmentVariable('OLLAMA_MODELS', 'User'))" -ForegroundColor White
