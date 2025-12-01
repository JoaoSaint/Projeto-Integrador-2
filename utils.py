import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from PIL import Image
import numpy as np

def contar_itens_lista(entradas, campo):
    contagem = {}

    for entrada in entradas:
        lista = getattr(entrada, campo, None)
        if not lista:
            continue

        if isinstance(lista, str):
            itens_brutos = lista.split(",")
        elif isinstance(lista, (list, tuple, set)):
            itens_brutos = list(lista)
        else:
            itens_brutos = [lista]

        itens_normalizados = []
        vistos = set()

        for item in itens_brutos:
            if item is None:
                continue

            valor = item.strip() if isinstance(item, str) else str(item).strip()
            if not valor:
                continue

            if valor in vistos:
                continue

            vistos.add(valor)
            itens_normalizados.append(valor)

        for item in itens_normalizados:
            contagem[item] = contagem.get(item, 0) + 1

    return contagem

def gerar_grafico(contagem, titulo, xlabel, ylabel='Quantidade', small=False, nomes_abaixo=False):
    """
    - contagem: dict com {categoria: valor}
    - titulo: título do gráfico
    - xlabel, ylabel: labels
    - small: True para dashboard (tamanho menor)
    - nomes_abaixo: True se nomes devem ficar fixos abaixo da barra (casos com poucas categorias)
    """
    categorias = list(contagem.keys())
    valores = list(contagem.values())

    # Ajuste do tamanho da figura
    if small:
        largura, altura = 5, 3.2
    else:
        largura = max(len(categorias) * 0.8, 6)
        altura = 6

    fig, ax = plt.subplots(figsize=(largura, altura))

    # Paleta de 13 cores distintas
    brand_colors = [
        '#556B2F', '#DAA520', '#8B4513', '#708090',
        '#6B8E23', '#FFD700', '#CD5C5C', '#4682B4',
        '#9ACD32', '#FF8C00', '#20B2AA', '#C71585', '#40E0D0'
    ]
    colors = [brand_colors[i % len(brand_colors)] for i in range(len(categorias))]

    barras = ax.bar(range(len(categorias)), valores, color=colors)

    ax.set_title(titulo, fontsize=11, fontweight='bold')
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_xlabel(xlabel, fontsize=9)

    # Remove ticks do eixo X
    ax.set_xticks(range(len(categorias)))

    # Posicionamento dos nomes
    if nomes_abaixo:
        # nomes abaixo da barra (casos com poucas categorias)
        ax.set_xticklabels(categorias, rotation=0, fontsize=9, ha='center')
        # colocar valor acima da barra
        for barra, valor in zip(barras, valores):
            ax.text(
                barra.get_x() + barra.get_width()/2,
                valor + max(valores)*0.02,
                str(valor),
                ha='center', va='bottom',
                fontsize=8, fontweight='bold'
            )
    else:
        # nomes dentro da barra, vertical
        ax.set_xticklabels(['']*len(categorias))  # remove rótulos do eixo
        max_chars = 15  # limite de caracteres antes de colocar "..."
        for barra, nome, valor in zip(barras, categorias, valores):
            # truncar somente aqui
            if len(nome) > max_chars:
                nome = nome[:max_chars] + "..."
            altura = barra.get_height()
            ax.text(
                barra.get_x() + barra.get_width()/2,
                altura/2,
                f"{nome}\n({valor})",
                ha='center', va='center',
                rotation=90,
                fontsize=8, fontweight='bold', color='black'
            )


    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', transparent=False)
    buf.seek(0)
    imagem_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    buf.close()
    plt.close(fig)
    return imagem_base64