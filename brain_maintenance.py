#!/usr/bin/env python3
"""
SEVERINO: Sistema de Manutenção do Cérebro
Compacta dados antigos sem perder informação crítica
"""

import sqlite3
import os
import time
import shutil
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("BrainMaintenance")

class BrainMaintenance:
    def __init__(self, db_path='sniper_brain.db', images_path='brain_images/'):
        self.db_path = db_path
        self.images_path = images_path
        
    def archive_old_data(self, days_threshold=30):
        """Arquiva dados antigos mantendo apenas amostras VÁLIDAS"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Timestamp limite (30 dias atrás)
            threshold = int(time.time()) - (days_threshold * 24 * 60 * 60)
            
            # Conta dados que serão arquivados
            c.execute("""
                SELECT COUNT(*) FROM raw_samples 
                WHERE timestamp_detection < ? AND ai_verdict = 'INVALID'
            """, (threshold,))
            
            count_to_archive = c.fetchone()[0]
            
            if count_to_archive > 0:
                # Move dados INVÁLIDOS antigos para tabela de arquivo
                c.execute("""
                    CREATE TABLE IF NOT EXISTS archived_samples AS 
                    SELECT * FROM raw_samples WHERE 1=0
                """)
                
                c.execute("""
                    INSERT INTO archived_samples 
                    SELECT * FROM raw_samples 
                    WHERE timestamp_detection < ? AND ai_verdict = 'INVALID'
                """, (threshold,))
                
                # Remove da tabela principal
                c.execute("""
                    DELETE FROM raw_samples 
                    WHERE timestamp_detection < ? AND ai_verdict = 'INVALID'
                """, (threshold,))
                
                conn.commit()
                logger.info(f"🗄️ Arquivados {count_to_archive} registros antigos (INVALID)")
                
            conn.close()
            
        except Exception as e:
            logger.error(f"Erro ao arquivar dados: {e}")
    
    def cleanup_old_images(self, days_threshold=15):
        """Remove imagens antigas mantendo apenas as de amostras VÁLIDAS"""
        try:
            if not os.path.exists(self.images_path):
                return
                
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Pega IDs de amostras válidas para preservar suas imagens
            c.execute("SELECT id FROM raw_samples WHERE ai_verdict = 'VALID'")
            valid_ids = {row[0] for row in c.fetchall()}
            
            threshold = time.time() - (days_threshold * 24 * 60 * 60)
            removed_count = 0
            
            for filename in os.listdir(self.images_path):
                if not filename.endswith('.png'):
                    continue
                    
                filepath = os.path.join(self.images_path, filename)
                
                # Verifica idade do arquivo
                if os.path.getctime(filepath) < threshold:
                    # Extrai ID do filename (formato: ID_SYMBOL_PATTERN.png)
                    try:
                        file_id = int(filename.split('_')[0])
                        
                        # Remove apenas se NÃO for uma amostra válida
                        if file_id not in valid_ids:
                            os.remove(filepath)
                            removed_count += 1
                            
                    except (ValueError, IndexError):
                        # Se não conseguir extrair ID, remove (arquivo malformado)
                        os.remove(filepath)
                        removed_count += 1
            
            conn.close()
            
            if removed_count > 0:
                logger.info(f"🧹 Removidas {removed_count} imagens antigas (preservadas as VÁLIDAS)")
                
        except Exception as e:
            logger.error(f"Erro ao limpar imagens: {e}")
    
    def get_database_stats(self):
        """Retorna estatísticas da database"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Estatísticas gerais
            c.execute("SELECT COUNT(*) FROM raw_samples")
            total = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM raw_samples WHERE ai_verdict = 'VALID'")
            valid = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM raw_samples WHERE ai_verdict = 'INVALID'")
            invalid = c.fetchone()[0]
            
            # Tamanho do arquivo
            db_size_mb = os.path.getsize(self.db_path) / (1024 * 1024)
            
            # Contagem de imagens
            image_count = 0
            if os.path.exists(self.images_path):
                image_count = len([f for f in os.listdir(self.images_path) if f.endswith('.png')])
            
            conn.close()
            
            return {
                'total_samples': total,
                'valid_samples': valid,
                'invalid_samples': invalid,
                'db_size_mb': round(db_size_mb, 2),
                'image_count': image_count
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return None
    
    def run_maintenance(self):
        """Executa manutenção completa"""
        logger.info("🔧 Iniciando manutenção do cérebro...")
        
        stats_before = self.get_database_stats()
        if stats_before:
            logger.info(f"📊 Antes: {stats_before['total_samples']} amostras, {stats_before['db_size_mb']}MB")
        
        # Arquiva dados antigos (preserva VÁLIDOS)
        self.archive_old_data(days_threshold=30)
        
        # Remove imagens antigas (preserva imagens de amostras VÁLIDAS)
        self.cleanup_old_images(days_threshold=15)
        
        stats_after = self.get_database_stats()
        if stats_after:
            logger.info(f"📊 Depois: {stats_after['total_samples']} amostras, {stats_after['db_size_mb']}MB")
            
        logger.info("✅ Manutenção concluída")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    maintenance = BrainMaintenance()
    maintenance.run_maintenance()