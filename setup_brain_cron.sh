#!/bin/bash
# SEVERINO: Script de configuração do Cron Job para treinamento da IA
# Executa treinamento automático a cada 12 horas

echo "🤖 CONFIGURANDO CRON JOB PARA TREINAMENTO DA IA"
echo "================================================"

# Diretório do projeto
PROJECT_DIR="/root/bot_sniper_bybit"
CRON_LOG="$PROJECT_DIR/brain_cron.log"

# Verificar se o diretório existe
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Diretório do projeto não encontrado: $PROJECT_DIR"
    exit 1
fi

# Criar entrada no crontab
echo "📅 Criando entrada no crontab..."
echo ""

# Primeiro, listar crontab atual
echo "📋 Crontab atual:"
crontab -l 2>/dev/null || echo "   (vazio)"
echo ""

# Adicionar novo job (executa a cada 12 horas)
CRON_JOB="0 */12 * * * cd $PROJECT_DIR && /usr/bin/python3 brain_training_cron.py --mode once >> $CRON_LOG 2>&1"

# Adicionar ao crontab
(crontab -l 2>/dev/null | grep -v "brain_training_cron.py"; echo "$CRON_JOB") | crontab -

echo "✅ Cron job configurado:"
echo "   $CRON_JOB"
echo ""

# Também configurar para executar na inicialização do sistema (opcional)
echo "⚙️ Configurando para executar na inicialização do sistema..."
SYSTEMD_SERVICE="/etc/systemd/system/brain-training.service"

cat > /tmp/brain-training.service << EOF
[Unit]
Description=Brain Training Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/python3 brain_training_cron.py --mode continuous
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Verificar se quer instalar o serviço systemd
read -p "📦 Instalar como serviço systemd? (s/N): " install_systemd

if [[ "$install_systemd" == "s" || "$install_systemd" == "S" ]]; then
    sudo cp /tmp/brain-training.service $SYSTEMD_SERVICE
    sudo systemctl daemon-reload
    sudo systemctl enable brain-training.service
    sudo systemctl start brain-training.service
    
    echo "✅ Serviço systemd instalado e iniciado"
    echo "   Comandos úteis:"
    echo "   - sudo systemctl status brain-training.service"
    echo "   - sudo journalctl -u brain-training.service -f"
    echo "   - sudo systemctl restart brain-training.service"
else
    echo "📝 Serviço systemd não instalado (apenas cron job)"
fi

echo ""
echo "🎯 CONFIGURAÇÃO COMPLETA"
echo "========================"
echo "📊 O sistema irá:"
echo "   1. Verificar a cada 12 horas se há 50+ feedbacks"
echo "   2. Executar treinamento automático quando critério atendido"
echo "   3. Manter logs em: $CRON_LOG"
echo ""
echo "🔍 Para verificar logs:"
echo "   tail -f $CRON_LOG"
echo ""
echo "🔄 Para executar manualmente:"
echo "   cd $PROJECT_DIR && python3 brain_training_cron.py --mode once"
echo ""
echo "📋 Para verificar crontab:"
echo "   crontab -l"
echo ""
echo "✅ Configuração concluída com sucesso!"