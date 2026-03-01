#!/bin/bash

echo "===================================================="
echo "🚀 PALAZZO FIORINI - Setup Script"
echo "===================================================="

# Crea directory per i log
mkdir -p /tmp/logs
touch /tmp/debug_ristorante.log

# Imposta permessi
chmod 777 /tmp/debug_ristorante.log

echo "✅ Setup completato!"
echo "===================================================="