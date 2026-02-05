import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, List, Tuple
from scipy import stats
from scipy.signal import argrelextrema

@dataclass
class PadraoDetectado:
    nome: str
    direcao: str  # "SHORT" ou "LONG"
    confiabilidade: float  # 0.0 a 1.0
    neckline_price: float
    target_price: float
    stop_loss_price: float
    timestamp: int

class AnalistaTecnico:
    """
    Detecta padrões gráficos clássicos com ranking por confiabilidade.
    
    Padrões implementados:
    - OCO (Ombro-Cabeça-Ombro) -> SHORT
    - OCO Invertido -> LONG
    - Topo Duplo -> SHORT
    - Fundo Duplo -> LONG
    - Triângulo Ascendente -> LONG
    - Triângulo Descendente -> SHORT
    - Triângulo Simétrico -> Ambos
    - Bandeira de Alta -> LONG
    - Bandeira de Baixa -> SHORT
    - Cunha Ascendente -> SHORT
    - Cunha Descendente -> LONG
    """
    
    def __init__(self):
        # Confiabilidade base por padrão (dados históricos aproximados)
        self.confiabilidade_base = {
            'OCO': 0.83,
            'OCO_INVERTIDO': 0.83,
            'TOPO_DUPLO': 0.78,
            'FUNDO_DUPLO': 0.78,
            'TRIANGULO_ASCENDENTE': 0.75,
            'TRIANGULO_DESCENDENTE': 0.75,
            'TRIANGULO_SIMETRICO': 0.70,
            'BANDEIRA_ALTA': 0.72,
            'BANDEIRA_BAIXA': 0.72,
            'CUNHA_ASCENDENTE': 0.68,
            'CUNHA_DESCENDENTE': 0.68,
        }

    def identificar_pivos(self, df: pd.DataFrame, order=3) -> Tuple[np.ndarray, np.ndarray]:
        """Identifica topos e fundos locais usando scipy."""
        highs = df['high'].values
        lows = df['low'].values
        
        # Indices dos topos e fundos locais
        top_idx = argrelextrema(highs, np.greater_equal, order=order)[0]
        bot_idx = argrelextrema(lows, np.less_equal, order=order)[0]
        
        return top_idx, bot_idx

    def calcular_tendencia(self, values: np.ndarray) -> Tuple[float, float]:
        """Retorna slope e r² da regressão linear."""
        if len(values) < 3:
            return 0, 0
        x = np.arange(len(values))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, values)
        return slope, r_value ** 2

    # ============================================================
    # PADRÃO 1: OCO (Ombro-Cabeça-Ombro) -> SHORT
    # ============================================================
    def verificar_oco(self, df: pd.DataFrame, top_idx: np.ndarray) -> Optional[PadraoDetectado]:
        """Detecta OCO clássico para entrada SHORT."""
        if len(top_idx) < 3:
            return None
            
        # Últimos 3 topos
        tops = [(i, df['high'].iloc[i]) for i in top_idx[-5:]]
        if len(tops) < 3:
            return None
            
        # Tenta encontrar formação OCO
        for i in range(len(tops) - 2):
            idx1, h1 = tops[i]      # Ombro Esquerdo
            idx2, h2 = tops[i + 1]  # Cabeça
            idx3, h3 = tops[i + 2]  # Ombro Direito
            
            # Regra 1: Cabeça mais alta que ombros
            if not (h2 > h1 and h2 > h3):
                continue
                
            # Regra 2: Simetria dos ombros (máx 8% diferença)
            diff_ombros = abs(h1 - h3) / max(h1, h3)
            if diff_ombros > 0.08:
                continue
                
            # Regra 3: Distância temporal razoável
            dist_total = idx3 - idx1
            if dist_total < 10 or dist_total > 100:
                continue
                
            # Calcular Neckline (mínimo entre os topos)
            neckline = df['low'].iloc[idx1:idx3+1].min()
            
            # Preço atual deve estar acima da neckline (padrão em formação)
            preco_atual = df['close'].iloc[-1]
            if preco_atual <= neckline or preco_atual >= h3:
                continue
                
            # Projeção do target
            altura = h2 - neckline
            target = neckline - altura
            stop = h3 * 1.015  # 1.5% acima do ombro direito
            
            # Ajuste de confiabilidade
            conf = self.confiabilidade_base['OCO']
            conf -= diff_ombros * 0.5  # Penaliza assimetria
            conf = max(0.60, min(0.95, conf))
            
            return PadraoDetectado(
                nome="OCO",
                direcao="SHORT",
                confiabilidade=conf,
                neckline_price=neckline,
                target_price=target,
                stop_loss_price=stop,
                timestamp=int(df.index[-1].timestamp())
            )
        return None

    # ============================================================
    # PADRÃO 2: OCO Invertido -> LONG
    # ============================================================
    def verificar_oco_invertido(self, df: pd.DataFrame, bot_idx: np.ndarray) -> Optional[PadraoDetectado]:
        """Detecta OCO Invertido para entrada LONG."""
        if len(bot_idx) < 3:
            return None
            
        bots = [(i, df['low'].iloc[i]) for i in bot_idx[-5:]]
        if len(bots) < 3:
            return None
            
        for i in range(len(bots) - 2):
            idx1, l1 = bots[i]      # Ombro Esquerdo
            idx2, l2 = bots[i + 1]  # Cabeça (mais baixa)
            idx3, l3 = bots[i + 2]  # Ombro Direito
            
            # Regra 1: Cabeça mais baixa que ombros
            if not (l2 < l1 and l2 < l3):
                continue
                
            # Regra 2: Simetria dos ombros
            diff_ombros = abs(l1 - l3) / max(l1, l3)
            if diff_ombros > 0.08:
                continue
                
            # Distância temporal
            dist_total = idx3 - idx1
            if dist_total < 10 or dist_total > 100:
                continue
                
            # Neckline (máximo entre os fundos)
            neckline = df['high'].iloc[idx1:idx3+1].max()
            
            preco_atual = df['close'].iloc[-1]
            if preco_atual >= neckline or preco_atual <= l3:
                continue
                
            altura = neckline - l2
            target = neckline + altura
            stop = l3 * 0.985  # 1.5% abaixo do ombro direito
            
            conf = self.confiabilidade_base['OCO_INVERTIDO']
            conf -= diff_ombros * 0.5
            conf = max(0.60, min(0.95, conf))
            
            return PadraoDetectado(
                nome="OCO_INVERTIDO",
                direcao="LONG",
                confiabilidade=conf,
                neckline_price=neckline,
                target_price=target,
                stop_loss_price=stop,
                timestamp=int(df.index[-1].timestamp())
            )
        return None

    # ============================================================
    # PADRÃO 3: Topo Duplo -> SHORT
    # ============================================================
    def verificar_topo_duplo(self, df: pd.DataFrame, top_idx: np.ndarray) -> Optional[PadraoDetectado]:
        """Detecta Topo Duplo (Double Top) para SHORT."""
        if len(top_idx) < 2:
            return None
            
        tops = [(i, df['high'].iloc[i]) for i in top_idx[-4:]]
        if len(tops) < 2:
            return None
            
        for i in range(len(tops) - 1):
            idx1, h1 = tops[i]
            idx2, h2 = tops[i + 1]
            
            # Regra 1: Topos similares (máx 3% diferença)
            diff = abs(h1 - h2) / max(h1, h2)
            if diff > 0.03:
                continue
                
            # Regra 2: Distância temporal adequada
            dist = idx2 - idx1
            if dist < 8 or dist > 60:
                continue
                
            # Neckline = mínimo entre os topos
            neckline = df['low'].iloc[idx1:idx2+1].min()
            
            preco_atual = df['close'].iloc[-1]
            if preco_atual <= neckline or preco_atual >= h2:
                continue
                
            altura = max(h1, h2) - neckline
            target = neckline - altura
            stop = max(h1, h2) * 1.01
            
            conf = self.confiabilidade_base['TOPO_DUPLO']
            conf -= diff * 2  # Penaliza diferença entre topos
            conf = max(0.60, min(0.90, conf))
            
            return PadraoDetectado(
                nome="TOPO_DUPLO",
                direcao="SHORT",
                confiabilidade=conf,
                neckline_price=neckline,
                target_price=target,
                stop_loss_price=stop,
                timestamp=int(df.index[-1].timestamp())
            )
        return None

    # ============================================================
    # PADRÃO 4: Fundo Duplo -> LONG
    # ============================================================
    def verificar_fundo_duplo(self, df: pd.DataFrame, bot_idx: np.ndarray) -> Optional[PadraoDetectado]:
        """Detecta Fundo Duplo (Double Bottom) para LONG."""
        if len(bot_idx) < 2:
            return None
            
        bots = [(i, df['low'].iloc[i]) for i in bot_idx[-4:]]
        if len(bots) < 2:
            return None
            
        for i in range(len(bots) - 1):
            idx1, l1 = bots[i]
            idx2, l2 = bots[i + 1]
            
            diff = abs(l1 - l2) / max(l1, l2)
            if diff > 0.03:
                continue
                
            dist = idx2 - idx1
            if dist < 8 or dist > 60:
                continue
                
            neckline = df['high'].iloc[idx1:idx2+1].max()
            
            preco_atual = df['close'].iloc[-1]
            if preco_atual >= neckline or preco_atual <= l2:
                continue
                
            altura = neckline - min(l1, l2)
            target = neckline + altura
            stop = min(l1, l2) * 0.99
            
            conf = self.confiabilidade_base['FUNDO_DUPLO']
            conf -= diff * 2
            conf = max(0.60, min(0.90, conf))
            
            return PadraoDetectado(
                nome="FUNDO_DUPLO",
                direcao="LONG",
                confiabilidade=conf,
                neckline_price=neckline,
                target_price=target,
                stop_loss_price=stop,
                timestamp=int(df.index[-1].timestamp())
            )
        return None

    # ============================================================
    # PADRÃO 5: Triângulo Ascendente -> LONG
    # ============================================================
    def verificar_triangulo_ascendente(self, df: pd.DataFrame, top_idx: np.ndarray, bot_idx: np.ndarray) -> Optional[PadraoDetectado]:
        """Triângulo Ascendente: topos planos + fundos ascendentes -> LONG."""
        if len(top_idx) < 2 or len(bot_idx) < 2:
            return None
            
        # Últimos topos e fundos
        tops = [df['high'].iloc[i] for i in top_idx[-4:]]
        bots = [df['low'].iloc[i] for i in bot_idx[-4:]]
        
        if len(tops) < 2 or len(bots) < 2:
            return None
            
        # Topos devem ser relativamente planos
        slope_tops, r2_tops = self.calcular_tendencia(np.array(tops))
        # Fundos devem ser ascendentes
        slope_bots, r2_bots = self.calcular_tendencia(np.array(bots))
        
        # Critérios
        avg_top = np.mean(tops)
        if abs(slope_tops / avg_top) > 0.001:  # Topos não planos
            return None
        if slope_bots <= 0:  # Fundos não ascendentes
            return None
            
        resistencia = max(tops)
        suporte = min(bots)
        preco_atual = df['close'].iloc[-1]
        
        if preco_atual >= resistencia or preco_atual <= suporte:
            return None
            
        altura = resistencia - suporte
        target = resistencia + altura * 0.8
        stop = suporte * 0.99
        
        conf = self.confiabilidade_base['TRIANGULO_ASCENDENTE']
        conf += r2_bots * 0.1  # Bonus por fundos bem alinhados
        conf = max(0.60, min(0.88, conf))
        
        return PadraoDetectado(
            nome="TRIANGULO_ASCENDENTE",
            direcao="LONG",
            confiabilidade=conf,
            neckline_price=resistencia,
            target_price=target,
            stop_loss_price=stop,
            timestamp=int(df.index[-1].timestamp())
        )

    # ============================================================
    # PADRÃO 6: Triângulo Descendente -> SHORT
    # ============================================================
    def verificar_triangulo_descendente(self, df: pd.DataFrame, top_idx: np.ndarray, bot_idx: np.ndarray) -> Optional[PadraoDetectado]:
        """Triângulo Descendente: fundos planos + topos descendentes -> SHORT."""
        if len(top_idx) < 2 or len(bot_idx) < 2:
            return None
            
        tops = [df['high'].iloc[i] for i in top_idx[-4:]]
        bots = [df['low'].iloc[i] for i in bot_idx[-4:]]
        
        if len(tops) < 2 or len(bots) < 2:
            return None
            
        slope_tops, r2_tops = self.calcular_tendencia(np.array(tops))
        slope_bots, r2_bots = self.calcular_tendencia(np.array(bots))
        
        avg_bot = np.mean(bots)
        if abs(slope_bots / avg_bot) > 0.001:  # Fundos não planos
            return None
        if slope_tops >= 0:  # Topos não descendentes
            return None
            
        resistencia = max(tops)
        suporte = min(bots)
        preco_atual = df['close'].iloc[-1]
        
        if preco_atual <= suporte or preco_atual >= resistencia:
            return None
            
        altura = resistencia - suporte
        target = suporte - altura * 0.8
        stop = resistencia * 1.01
        
        conf = self.confiabilidade_base['TRIANGULO_DESCENDENTE']
        conf += r2_tops * 0.1
        conf = max(0.60, min(0.88, conf))
        
        return PadraoDetectado(
            nome="TRIANGULO_DESCENDENTE",
            direcao="SHORT",
            confiabilidade=conf,
            neckline_price=suporte,
            target_price=target,
            stop_loss_price=stop,
            timestamp=int(df.index[-1].timestamp())
        )

    # ============================================================
    # PADRÃO 7: Triângulo Simétrico -> Ambos (usa tendência prévia)
    # ============================================================
    def verificar_triangulo_simetrico(self, df: pd.DataFrame, top_idx: np.ndarray, bot_idx: np.ndarray) -> Optional[PadraoDetectado]:
        """Triângulo Simétrico: topos descendentes + fundos ascendentes."""
        if len(top_idx) < 2 or len(bot_idx) < 2:
            return None
            
        tops = [df['high'].iloc[i] for i in top_idx[-4:]]
        bots = [df['low'].iloc[i] for i in bot_idx[-4:]]
        
        if len(tops) < 2 or len(bots) < 2:
            return None
            
        slope_tops, r2_tops = self.calcular_tendencia(np.array(tops))
        slope_bots, r2_bots = self.calcular_tendencia(np.array(bots))
        
        # Topos descendentes E fundos ascendentes
        if slope_tops >= 0 or slope_bots <= 0:
            return None
            
        # Determina direção pela tendência prévia (20 candles antes)
        preco_inicio = df['close'].iloc[0:10].mean()
        preco_meio = df['close'].iloc[-30:-20].mean() if len(df) > 30 else preco_inicio
        
        if preco_meio > preco_inicio:
            direcao = "LONG"  # Tendência prévia de alta = rompe pra cima
        else:
            direcao = "SHORT"
            
        resistencia = max(tops)
        suporte = min(bots)
        preco_atual = df['close'].iloc[-1]
        
        if preco_atual <= suporte or preco_atual >= resistencia:
            return None
            
        altura = resistencia - suporte
        
        if direcao == "LONG":
            target = resistencia + altura * 0.7
            stop = suporte * 0.99
            neckline = resistencia
        else:
            target = suporte - altura * 0.7
            stop = resistencia * 1.01
            neckline = suporte
            
        conf = self.confiabilidade_base['TRIANGULO_SIMETRICO']
        conf = max(0.55, min(0.80, conf))
        
        return PadraoDetectado(
            nome="TRIANGULO_SIMETRICO",
            direcao=direcao,
            confiabilidade=conf,
            neckline_price=neckline,
            target_price=target,
            stop_loss_price=stop,
            timestamp=int(df.index[-1].timestamp())
        )

    # ============================================================
    # PADRÃO 8: Bandeira de Alta (Bull Flag) -> LONG
    # ============================================================
    def verificar_bandeira_alta(self, df: pd.DataFrame) -> Optional[PadraoDetectado]:
        """Bandeira de Alta: forte alta + consolidação descendente -> LONG."""
        if len(df) < 30:
            return None
            
        # Busca impulso de alta (mastro)
        janela_mastro = df.iloc[-50:-15] if len(df) > 50 else df.iloc[:-15]
        if len(janela_mastro) < 10:
            return None
            
        retorno_mastro = (janela_mastro['close'].iloc[-1] - janela_mastro['close'].iloc[0]) / janela_mastro['close'].iloc[0]
        
        if retorno_mastro < 0.05:  # Precisa de pelo menos 5% de alta
            return None
            
        # Consolidação (bandeira) - últimos 15 candles
        bandeira = df.iloc[-15:]
        slope_band, r2_band = self.calcular_tendencia(bandeira['close'].values)
        
        # Bandeira deve ter leve inclinação para baixo
        if slope_band >= 0:
            return None
            
        # Volatilidade na bandeira deve ser menor que no mastro
        vol_mastro = janela_mastro['close'].std() / janela_mastro['close'].mean()
        vol_bandeira = bandeira['close'].std() / bandeira['close'].mean()
        
        if vol_bandeira > vol_mastro * 0.8:
            return None
            
        topo_mastro = janela_mastro['high'].max()
        base_bandeira = bandeira['low'].min()
        preco_atual = df['close'].iloc[-1]
        
        altura_mastro = topo_mastro - janela_mastro['low'].min()
        target = topo_mastro + altura_mastro * 0.6
        stop = base_bandeira * 0.99
        
        conf = self.confiabilidade_base['BANDEIRA_ALTA']
        conf += retorno_mastro * 0.5  # Bonus por mastro forte
        conf = max(0.60, min(0.85, conf))
        
        return PadraoDetectado(
            nome="BANDEIRA_ALTA",
            direcao="LONG",
            confiabilidade=conf,
            neckline_price=topo_mastro,
            target_price=target,
            stop_loss_price=stop,
            timestamp=int(df.index[-1].timestamp())
        )

    # ============================================================
    # PADRÃO 9: Bandeira de Baixa (Bear Flag) -> SHORT
    # ============================================================
    def verificar_bandeira_baixa(self, df: pd.DataFrame) -> Optional[PadraoDetectado]:
        """Bandeira de Baixa: forte queda + consolidação ascendente -> SHORT."""
        if len(df) < 30:
            return None
            
        janela_mastro = df.iloc[-50:-15] if len(df) > 50 else df.iloc[:-15]
        if len(janela_mastro) < 10:
            return None
            
        retorno_mastro = (janela_mastro['close'].iloc[-1] - janela_mastro['close'].iloc[0]) / janela_mastro['close'].iloc[0]
        
        if retorno_mastro > -0.05:  # Precisa de pelo menos 5% de queda
            return None
            
        bandeira = df.iloc[-15:]
        slope_band, r2_band = self.calcular_tendencia(bandeira['close'].values)
        
        if slope_band <= 0:  # Bandeira deve subir levemente
            return None
            
        vol_mastro = janela_mastro['close'].std() / janela_mastro['close'].mean()
        vol_bandeira = bandeira['close'].std() / bandeira['close'].mean()
        
        if vol_bandeira > vol_mastro * 0.8:
            return None
            
        fundo_mastro = janela_mastro['low'].min()
        topo_bandeira = bandeira['high'].max()
        preco_atual = df['close'].iloc[-1]
        
        altura_mastro = janela_mastro['high'].max() - fundo_mastro
        target = fundo_mastro - altura_mastro * 0.6
        stop = topo_bandeira * 1.01
        
        conf = self.confiabilidade_base['BANDEIRA_BAIXA']
        conf += abs(retorno_mastro) * 0.5
        conf = max(0.60, min(0.85, conf))
        
        return PadraoDetectado(
            nome="BANDEIRA_BAIXA",
            direcao="SHORT",
            confiabilidade=conf,
            neckline_price=fundo_mastro,
            target_price=target,
            stop_loss_price=stop,
            timestamp=int(df.index[-1].timestamp())
        )

    # ============================================================
    # PADRÃO 10: Cunha Ascendente -> SHORT (reversão)
    # ============================================================
    def verificar_cunha_ascendente(self, df: pd.DataFrame, top_idx: np.ndarray, bot_idx: np.ndarray) -> Optional[PadraoDetectado]:
        """Cunha Ascendente: topos e fundos subindo, mas convergindo -> SHORT."""
        if len(top_idx) < 3 or len(bot_idx) < 3:
            return None
            
        tops = [df['high'].iloc[i] for i in top_idx[-5:]]
        bots = [df['low'].iloc[i] for i in bot_idx[-5:]]
        
        if len(tops) < 3 or len(bots) < 3:
            return None
            
        slope_tops, r2_tops = self.calcular_tendencia(np.array(tops))
        slope_bots, r2_bots = self.calcular_tendencia(np.array(bots))
        
        # Ambos devem subir
        if slope_tops <= 0 or slope_bots <= 0:
            return None
            
        # Fundos devem subir mais rápido (convergência)
        if slope_bots <= slope_tops:
            return None
            
        suporte = min(bots)
        resistencia = max(tops)
        preco_atual = df['close'].iloc[-1]
        
        if preco_atual <= suporte or preco_atual >= resistencia:
            return None
            
        altura = resistencia - suporte
        target = suporte - altura * 0.5
        stop = resistencia * 1.015
        
        conf = self.confiabilidade_base['CUNHA_ASCENDENTE']
        conf += (r2_tops + r2_bots) * 0.05
        conf = max(0.55, min(0.80, conf))
        
        return PadraoDetectado(
            nome="CUNHA_ASCENDENTE",
            direcao="SHORT",
            confiabilidade=conf,
            neckline_price=suporte,
            target_price=target,
            stop_loss_price=stop,
            timestamp=int(df.index[-1].timestamp())
        )

    # ============================================================
    # PADRÃO 11: Cunha Descendente -> LONG (reversão)
    # ============================================================
    def verificar_cunha_descendente(self, df: pd.DataFrame, top_idx: np.ndarray, bot_idx: np.ndarray) -> Optional[PadraoDetectado]:
        """Cunha Descendente: topos e fundos caindo, mas convergindo -> LONG."""
        if len(top_idx) < 3 or len(bot_idx) < 3:
            return None
            
        tops = [df['high'].iloc[i] for i in top_idx[-5:]]
        bots = [df['low'].iloc[i] for i in bot_idx[-5:]]
        
        if len(tops) < 3 or len(bots) < 3:
            return None
            
        slope_tops, r2_tops = self.calcular_tendencia(np.array(tops))
        slope_bots, r2_bots = self.calcular_tendencia(np.array(bots))
        
        # Ambos devem cair
        if slope_tops >= 0 or slope_bots >= 0:
            return None
            
        # Topos devem cair mais rápido (convergência)
        if slope_tops >= slope_bots:
            return None
            
        suporte = min(bots)
        resistencia = max(tops)
        preco_atual = df['close'].iloc[-1]
        
        if preco_atual <= suporte or preco_atual >= resistencia:
            return None
            
        altura = resistencia - suporte
        target = resistencia + altura * 0.5
        stop = suporte * 0.985
        
        conf = self.confiabilidade_base['CUNHA_DESCENDENTE']
        conf += (r2_tops + r2_bots) * 0.05
        conf = max(0.55, min(0.80, conf))
        
        return PadraoDetectado(
            nome="CUNHA_DESCENDENTE",
            direcao="LONG",
            confiabilidade=conf,
            neckline_price=resistencia,
            target_price=target,
            stop_loss_price=stop,
            timestamp=int(df.index[-1].timestamp())
        )

    # ============================================================
    # MÉTODO PRINCIPAL: Analisa par e retorna MELHOR padrão
    # ============================================================
    def analisar_par(self, symbol: str, candles: list) -> Optional[PadraoDetectado]:
        """
        Analisa todos os padrões e retorna o de MAIOR CONFIABILIDADE.
        """
        try:
            df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            if len(df) < 30:
                return None
                
            # Identificar pivôs
            top_idx, bot_idx = self.identificar_pivos(df, order=3)
            
            # Lista para armazenar todos os padrões encontrados
            padroes_encontrados: List[PadraoDetectado] = []
            
            # Verifica cada padrão
            verificacoes = [
                lambda: self.verificar_oco(df, top_idx),
                lambda: self.verificar_oco_invertido(df, bot_idx),
                lambda: self.verificar_topo_duplo(df, top_idx),
                lambda: self.verificar_fundo_duplo(df, bot_idx),
                lambda: self.verificar_triangulo_ascendente(df, top_idx, bot_idx),
                lambda: self.verificar_triangulo_descendente(df, top_idx, bot_idx),
                lambda: self.verificar_triangulo_simetrico(df, top_idx, bot_idx),
                lambda: self.verificar_bandeira_alta(df),
                lambda: self.verificar_bandeira_baixa(df),
                lambda: self.verificar_cunha_ascendente(df, top_idx, bot_idx),
                lambda: self.verificar_cunha_descendente(df, top_idx, bot_idx),
            ]
            
            for verificar in verificacoes:
                try:
                    padrao = verificar()
                    if padrao:
                        padroes_encontrados.append(padrao)
                except Exception as e:
                    continue
                    
            if not padroes_encontrados:
                return None
                
            # Retorna o padrão com MAIOR confiabilidade
            melhor = max(padroes_encontrados, key=lambda p: p.confiabilidade)
            return melhor
            
        except Exception as e:
            print(f"Erro na analise tecnica de {symbol}: {e}")
            return None
