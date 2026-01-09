import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Club Analytics Pro", layout="wide", page_icon="⚽")

# --- LISTA DE EQUIPOS ---
# IMPORTANTE: Pon aquí los nombres EXACTOS de las pestañas de tu Google Sheet

lista_equipos = {
    "Preferente": "1039572604", "Juvenil A": "689736481",
    "Juvenil B": "1086115076", "Cadete A": "325576234",
    "Cadete B": "0", "Infantil A": "1612741636",
    "Infantil B": "1284204032"   
}

# --- CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Recuperamos la URL de los secretos para evitar el error que tuviste
try:
    url_sheet = st.secrets["connections"]["gsheets"]["spreadsheet"]
except:
    st.error("No se encuentra la URL en secrets.toml")
    st.stop()

@st.cache_data(ttl=60)
def cargar_datos_equipo(nombre_hoja,gid):
    # Leemos la pestaña específica usando 'worksheet'
    try:
        df = conn.read(spreadsheet=url_sheet, worksheet=gid, header=[0, 1])
    except Exception as e:
        return None, None, f"Error al leer la hoja '{nombre_hoja}': {str(e)}"

    df = df.fillna(0)
    # Limpiar filas vacías
    df = df[df[df.columns[0]].astype(str) != '0']
    df.index = df.iloc[:, 0] # Nombre del jugador como índice
    
    # --- CÁLCULOS ---
    # 1. Detectar métricas buscando en el nivel 1 de columnas (T, S, G, A, R)
    # Usamos .xs para extraer secciones transversales del MultiIndex
    try:

        t_partido=np.max(df.loc(axis=1)[:,'T'])

        min_tit = df.xs('T', axis=1, level=1).sum(axis=1)
        min_sup = df.xs('S', axis=1, level=1).sum(axis=1)
        min_tot = min_tit + min_sup

        part_tit=(df.loc(axis=1)[:,'T']>0).to_numpy().sum(axis=1)
        part_sup=(df.loc(axis=1)[:,'S']>0).to_numpy().sum(axis=1)
        part_comp=(df.loc(axis=1)[:,'T']==t_partido).to_numpy().sum(axis=1)
        part_tot=part_tit+part_sup

        min_posibles_jugador = part_tot * t_partido

        jornadas_con_datos = df.xs('T', axis=1, level=1).columns[df.xs('T', axis=1, level=1).sum() > 0]
        n_jornadas=len(jornadas_con_datos)

        min_totales_equipo = n_jornadas * t_partido

        g_tot = df.xs('G', axis=1, level=1).sum(axis=1)
        a_tot = df.xs('A', axis=1, level=1).sum(axis=1)
        r_tot = df.xs('R', axis=1, level=1).sum(axis=1)
        
        g_x_min = min_tot / g_tot 
        g_x_min[g_x_min==np.inf]=0
        
        a_x_min = min_tot / a_tot 
        a_x_min[a_x_min==np.inf]=0

        r_x_min = min_tot / r_tot 
        r_x_min[r_x_min==np.inf]=0
       
        # Porcentaje de participación
        pct_participacion_disp = (min_tot / min_posibles_jugador) * 100 # Porcentaje de minutos jugados de los partidos que ha participado
        pct_participacion_equipo = (min_tot / min_totales_equipo) * 100 # Porcentaje de minutos jugados con respecto al total.
        
    except KeyError:
        return None, None, "La hoja no tiene la estructura correcta (Faltan columnas T, S, G, A o R)"

    # DataFrame Resumen
    df_resumen = pd.DataFrame({
        'min_tit': min_tit,
        'min_sup': min_sup,
        'min_tot': min_tot,
        'part_tit': part_tit,
        'part_sup': part_sup,
        'part_comp': part_comp,
        'part_tot': part_tot,
        'goles': g_tot,
        'goles_x_minuto': g_x_min,
        'amarillas': a_tot,
        'amarillas_x_minuto': a_x_min,
        'rojas': r_tot,
        'rojas_por_minuto': r_x_min,
        'pct_jugado': pct_participacion_disp,
        'pct_jugado_equipo': pct_participacion_equipo
    }, index=df.index)
    
    return df, df_resumen, None


# --- INTERFAZ ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/53/53283.png", width=100)
st.sidebar.title("Panel Técnico")


# 1. SELECTOR DE EQUIPO
equipo_seleccionado = st.sidebar.selectbox("Seleccionar Equipo", lista_equipos)

if st.sidebar.button("🔄 Actualizar Datos"):
    st.cache_data.clear()
    st.rerun()


# Cargar datos
df_full, df_stats, error = cargar_datos_equipo(equipo_seleccionado,lista_equipos[equipo_seleccionado])

if error:
    st.error(error)
else:
    # --- ENCABEZADO Y KPIs ---
    st.title(f"Informe: {equipo_seleccionado}")
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Goles a Favor", int(df_stats['goles'].sum()))
    kpi2.metric("Tarjetas Amarillas", int(df_stats['amarillas'].sum()))
    kpi3.metric("Plantilla", f"{len(df_stats)} jug.")
    
    jornadas_con_datos = df_full.xs('T', axis=1, level=1).columns[df_full.xs('T', axis=1, level=1).sum() > 0]
    n_jornadas=len(jornadas_con_datos)
    #partidos_est = int(df_stats['min_tot'].max() / 90)
    kpi4.metric("Jornadas ", n_jornadas)

    st.markdown("---")

    # --- SECCIÓN 1: SEMÁFORO DE MINUTOS ---
    st.subheader("🚦 Estado de la Plantilla (Minutos Jugados)")
    
    # Clasificación
    df_stats['Rol_jugador'] = pd.cut(df_stats['pct_jugado'], 
                             bins=[-1, 30, 70, 1000], 
                             labels=['Rojo (<30%)', 'Naranja (30-70%)', 'Verde (>70%)'])
    
    df_stats['Rol_jugador_equipo'] = pd.cut(df_stats['pct_jugado_equipo'], 
                             bins=[-1, 30, 70, 1000], 
                             labels=['Rojo (<30%)', 'Naranja (30-70%)', 'Verde (>70%)'])
    
    col_sem1, col_sem2 = st.columns([2, 1])
    
    with col_sem1:
        # Gráfico de barras coloreado por condición
        fig_sem = px.bar(df_stats, 
                         y='pct_jugado', 
                         x=df_stats.index, 
                         color='Rol_jugador',
                         color_discrete_map={
                             'Verde (>70%)': '#2ecc71', 
                             'Naranja (30-70%)': '#f39c12', 
                             'Rojo (<30%)': '#e74c3c'
                         },
                         title="Porcentaje de minutos jugados de los disponibles",
                         labels={'y': '% Minutos', 'index': 'Jugador'},
                         template="plotly_dark")
        fig_sem.update_layout(xaxis={'categoryorder':'total descending'})
        st.plotly_chart(fig_sem, use_container_width=True)
        
    with col_sem2:
        # Donut del reparto de roles
        fig_rol = px.pie(df_stats, names='Rol_jugador', 
                         title="Distribución de Roles",
                         color='Rol_jugador',
                         color_discrete_map={
                             'Verde (>70%)': '#2ecc71', 
                             'Naranja (30-70%)': '#f39c12', 
                             'Rojo (<30%)': '#e74c3c'
                         },
                         template="plotly_dark", hole=0.4)
        st.plotly_chart(fig_rol, use_container_width=True)


    col_sem1, col_sem2 = st.columns([2, 1])
    
    with col_sem1:
        # Gráfico de barras coloreado por condición
        fig_sem = px.bar(df_stats, 
                         y='pct_jugado_equipo', 
                         x=df_stats.index, 
                         color='Rol_jugador_equipo',
                         color_discrete_map={
                             'Verde (>70%)': '#2ecc71', 
                             'Naranja (30-70%)': '#f39c12', 
                             'Rojo (<30%)': '#e74c3c'
                         },
                         title="Porcentaje de minutos jugados de los totales",
                         labels={'y': '% Minutos', 'index': 'Jugador'},
                         template="plotly_dark")
        fig_sem.update_layout(xaxis={'categoryorder':'total descending'})
        st.plotly_chart(fig_sem, use_container_width=True)
        
    with col_sem2:
        # Donut del reparto de roles
        fig_rol = px.pie(df_stats, names='Rol_jugador_equipo', 
                         title="Distribución de Roles",
                         color='Rol_jugador_equipo',
                         color_discrete_map={
                             'Verde (>70%)': '#2ecc71', 
                             'Naranja (30-70%)': '#f39c12', 
                             'Rojo (<30%)': '#e74c3c'
                         },
                         template="plotly_dark", hole=0.4)
        st.plotly_chart(fig_rol, use_container_width=True)


    st.markdown("---")

    # --- SECCIÓN 2: RENDIMIENTO OFENSIVO Y DISCIPLINARIO ---
    c_goles, c_tarj = st.columns(2)
    
    with c_goles:
        st.subheader("⚽ Goleadores")
        df_goles = df_stats[df_stats['goles'] > 0].sort_values('goles', ascending=True)
        if not df_goles.empty:
            fig_g = px.bar(df_goles, x='goles', y=df_goles.index, orientation='h',
                           text='goles', color='goles', color_continuous_scale='Blues',
                           template="plotly_dark")
            st.plotly_chart(fig_g, use_container_width=True)
        else:
            st.info("Aún no hay goles registrados.")

    with c_tarj:
        st.subheader("🟨 Disciplina")
        df_ama = df_stats[df_stats['amarillas'] > 0].sort_values('amarillas', ascending=True)
        if not df_ama.empty:
            fig_a = px.bar(df_ama, x='amarillas', y=df_ama.index, orientation='h',
                           text='amarillas', color='amarillas', color_continuous_scale='YlOrRd',
                           template="plotly_dark")
            st.plotly_chart(fig_a, use_container_width=True)
        else:
            st.info("Equipo limpio: 0 tarjetas.")

    # --- SECCIÓN 3: DETALLE JUGADOR ---
    st.markdown("---")
    jugador = st.selectbox("🔍 Analizar Jugador Específico", df_stats.index)
    
    if jugador:
        # Extraemos datos de jornadas
        min_t_evo = df_full.loc[jugador].xs('T', level=1)
        min_s_evo = df_full.loc[jugador].xs('S', level=1)
        jornadas = [f"J{i+1}" for i in range(len(min_t_evo))]

        fig_evo = go.Figure()
        fig_evo.add_trace(go.Bar(name='Titular', x=jornadas, y=min_t_evo, marker_color='#2ecc71'))
        fig_evo.add_trace(go.Bar(name='Suplente', x=jornadas, y=min_s_evo, marker_color='#f1c40f'))
        
        fig_evo.update_layout(barmode='stack', title=f"Minutos por Jornada: {jugador}", 
                              template="plotly_dark", yaxis_title="Minutos")
        st.plotly_chart(fig_evo, use_container_width=True)

    # --- SECCIÓN 4: COMPARADOR HEAD-TO-HEAD ---
    st.markdown("---")
    st.subheader("⚔️ Comparador de Jugadores")
    
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        p1 = st.selectbox("Jugador A", df_stats.index, index=0)
    with col_sel2:
        # Intentamos que por defecto seleccione al segundo de la lista
        p2 = st.selectbox("Jugador B", df_stats.index, index=1 if len(df_stats) > 1 else 0)

    if p1 and p2:
        # Extraer datos
        stats_p1 = df_stats.loc[p1]
        stats_p2 = df_stats.loc[p2]
        
        # 1. TABLA COMPARATIVA CENTRAL
        # Usamos columnas para crear un efecto de "Marcador"
        c_p1, c_metric, c_p2 = st.columns([1, 1, 1])
        
        # Función auxiliar para mostrar métricas con colores
        def mostrar_comparacion(label, val1, val2, es_mejor_alto=True):
            delta_1 = val1 - val2
            delta_2 = val2 - val1
            
            # Definir color según quien gana
            color_p1 = "normal"
            color_p2 = "normal"
            
            if val1 != val2:
                if (es_mejor_alto and val1 > val2) or (not es_mejor_alto and val1 < val2):
                    color_p1 = "off" # Streamlit usa "off" o "inverse" para resaltar verde en deltas
                    color_p2 = "normal" # Rojo/Gris
                else:
                    color_p1 = "normal"
                    color_p2 = "off"

            c_p1.metric(label, int(val1), delta=int(delta_1), delta_color=color_p1)
            c_p2.metric(label, int(val2), delta=int(delta_2), delta_color=color_p2)
            c_metric.markdown(f"<h3 style='text-align: center; vertical-align: middle; margin-top: 20px'>{label}</h3>", unsafe_allow_html=True)

        # Renderizar métricas
        mostrar_comparacion("Minutos Totales", stats_p1['min_tot'], stats_p2['min_tot'])
        st.write("") # Espaciador
        mostrar_comparacion("Goles", stats_p1['goles'], stats_p2['goles'])
        st.write("")
        mostrar_comparacion("Amarillas", stats_p1['amarillas'], stats_p2['amarillas'], es_mejor_alto=False) # Menos es mejor

        # 2. GRÁFICO DE BARRAS COMPARATIVO
        st.write("")
        st.write("")
        
        fig_comp = go.Figure()
        metricas = ['Min. Titular', 'Min. Suplente', 'Goles (x100)', 'Amarillas (x100)']
        
        # Escalamos goles y amarillas x100 solo para que se vean en la gráfica junto a los minutos
        # (Esto es un truco visual, puedes quitarlo si prefieres normalizar de otra forma)
        vals_1 = [stats_p1['min_tit'], stats_p1['min_sup'], stats_p1['goles']*100, stats_p1['amarillas']*100]
        vals_2 = [stats_p2['min_tit'], stats_p2['min_sup'], stats_p2['goles']*100, stats_p2['amarillas']*100]

        fig_comp.add_trace(go.Bar(name=p1, x=metricas, y=vals_1, marker_color='#3498db'))
        fig_comp.add_trace(go.Bar(name=p2, x=metricas, y=vals_2, marker_color='#e74c3c'))

        fig_comp.update_layout(barmode='group', title="Comparativa Directa", template="plotly_dark")
        st.plotly_chart(fig_comp, use_container_width=True)
        st.caption("*Nota: Goles y Amarillas multiplicados x100 para visibilidad gráfica")



            # --- EXTRA 1: GRÁFICO DE EFICIENCIA (SCATTER PLOT) ---
        st.subheader("🎯 Eficiencia: Goles vs Minutos")
        
        # Filtramos para no ensuciar el gráfico con gente que no juega
        df_eficiencia = df_stats[df_stats['min_tot'] > 90].copy() 
        
        # Calculamos Goles por 90 min para el tamaño de la burbuja o el color
        df_eficiencia['goles_90'] = (df_eficiencia['goles'] / df_eficiencia['min_tot']) * 90
        
        fig_eff = px.scatter(df_eficiencia, 
                            x='min_tot', 
                            y='goles',
                            size='goles_90', # El tamaño de la bola es su promedio goleador
                            color='goles',
                            hover_name=df_eficiencia.index,
                            text=df_eficiencia.index,
                            title="Relación Minutos jugados vs Goles marcados (Tamaño = Goles/90min)",
                            labels={'min_tot': 'Minutos Totales', 'goles': 'Goles Totales'},
                            template="plotly_dark")
        
        fig_eff.update_traces(textposition='top center')
        st.plotly_chart(fig_eff, use_container_width=True)



        # --- EXTRA 2: RADAR CHART (Sustituye el gráfico de barras del comparador por esto) ---
        st.write("---")
        st.subheader("🕸️ Comparativa Visual (Radar)")
        
        # 1. Normalización de datos (0-100) respecto al MÁXIMO DEL EQUIPO
        # Esto es vital para que el gráfico se vea bien
        def normalizar(valor, columna):
            max_val = df_stats[columna].max()
            if max_val == 0: return 0
            return (valor / max_val) * 100

        metricas_radar = ['min_tot', 'goles', 'pct_jugado_equipo', 'part_tit']
        nombres_radar = ['Minutos', 'Goles', '% Participación', 'Titularidades']
        
        vals_p1_norm = [normalizar(stats_p1[m], m) for m in metricas_radar]
        vals_p2_norm = [normalizar(stats_p2[m], m) for m in metricas_radar]
        
        # Cerrar el círculo del radar añadiendo el primer valor al final
        vals_p1_norm += [vals_p1_norm[0]]
        vals_p2_norm += [vals_p2_norm[0]]
        nombres_radar += [nombres_radar[0]]

        fig_radar = go.Figure()

        fig_radar.add_trace(go.Scatterpolar(
              r=vals_p1_norm,
              theta=nombres_radar,
              fill='toself',
              name=p1,
              line_color='#3498db'
        ))
        fig_radar.add_trace(go.Scatterpolar(
              r=vals_p2_norm,
              theta=nombres_radar,
              fill='toself',
              name=p2,
              line_color='#e74c3c'
        ))

        fig_radar.update_layout(
          polar=dict(
            radialaxis=dict(
              visible=True,
              range=[0, 100] # Siempre de 0 a 100% relativo al equipo
            )),
          showlegend=True,
          template="plotly_dark",
          title="Comparativa Relativa (Escala 0-100 sobre el mejor del equipo)"
        )
        st.plotly_chart(fig_radar, use_container_width=True)



        # --- EXTRA 3: RACHA ÚLTIMOS 5 PARTIDOS ---
        st.subheader("🔥 Estado de Forma (Últimos 5 partidos)")
        
        # Obtenemos las últimas 5 columnas de datos de Titular y Suplente
        # Usamos iloc para coger las últimas 5 columnas del nivel 1 ('T' y 'S')
        last_5_t = df_full.loc[jugador].xs('T', level=1).iloc[n_jornadas-5:n_jornadas]
        last_5_s = df_full.loc[jugador].xs('S', level=1).iloc[n_jornadas-5:n_jornadas]
        
        min_last_5 = last_5_t.sum() + last_5_s.sum()
        max_possible_5 = 5 * 90 # Asumiendo 90 min por partido
        pct_forma = (min_last_5 / max_possible_5) * 100
        
        c_forma1, c_forma2 = st.columns([1,3])
        c_forma1.metric("Minutos (Últ. 5)", int(min_last_5), f"{int(pct_forma)}% Disp.")
        
        # Mini gráfico de tendencia (Sparkline)
        df_forma = pd.DataFrame({'Jornada': last_5_t.index, 'Minutos': last_5_t.values + last_5_s.values})
        fig_spark = px.line(df_forma, x='Jornada', y='Minutos', markers=True, template="plotly_dark")
        fig_spark.update_layout(height=150, margin=dict(l=20, r=20, t=20, b=20), yaxis_range=[0, 95])
        c_forma2.plotly_chart(fig_spark, use_container_width=True)



        import streamlit as st

        # ... tu código de carga y cálculos donde generas df_stats ...

        st.subheader("Verificación de Datos Calculados (df_stats)")

        # Opción Recomendada: Tabla interactiva (puedes ordenar y filtrar)
        st.dataframe(df_stats, use_container_width=True)