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
    # 1. CARGA CON DOBLE CABECERA
    # Leemos las dos primeras filas como encabezados
    # Leemos la pestaña específica usando 'worksheet'
    try:
        df = conn.read(spreadsheet=url_sheet, worksheet=gid, header=[0, 1])
    except Exception as e:
        return None, None, f"Error al leer la hoja '{nombre_hoja}': {str(e)}"

    # 2. LIMPIEZA Y ESTRUCTURA (ACTUALIZADO)
    # En lugar de buscar "Name" o "Nombre" por texto, cogemos las dos primeras columnas por posición.
    # Así, si vuelves a cambiar el título en el Excel, el código no se rompe.
    cols_indice = df.columns[:2].tolist() 
    df = df.set_index(cols_indice)

    # Asignamos los nombres internos que usaremos en el código
    df.index.names = ['Nombre', 'Posición']

    # 3. TRANSFORMAR DE ANCHO A LARGO
    # Bajamos la cabecera de las jornadas (Nivel 0) a una columna. Esto genera un df con una unica cabecera y más filas (repitiendo nombres)
    df_long = df.stack(level=0)

    # Reseteamos índice para trabajar con columnas normales
    df_long = df_long.reset_index()
    df_long.rename(columns={'level_2': 'Jornada'}, inplace=True)

    # 4. LIMPIEZA DE DATOS NUMÉRICOS
    # Convertimos todo a números; lo que no sea número (texto, vacíos) será 0
    cols_stats = ['C_NC', 'T', 'S', 'G', 'A', 'DA', 'R']
    for col in cols_stats:
        df_long[col] = pd.to_numeric(df_long[col], errors='coerce').fillna(0)

    # 5. CÁLCULOS
    # Minutos totales y comprobaciones lógicas
    t_partido=np.max(df_long['T'])
    df_long['Minutos totales'] = df_long['T'] + df_long['S']
    df_long['Jugados'] = np.where(df_long['Minutos totales'] > 0, 1, 0)
    df_long['Titular'] = np.where(df_long['T'] > 0, 1, 0)
    df_long['Suplente'] = np.where(df_long['S'] > 0, 1, 0)
    df_long['Completos'] = np.where(df_long['T'] == t_partido, 1, 0)
    
    # 6. AGRUPAR POR JUGADOR (Estadísticas de Temporada)
    df_stats = df_long.groupby(['Nombre', 'Posición']).agg({
        'C_NC': 'sum',            # Convocatorias
        'Jugados': 'sum',          # Partidos Jugados
        'Titular': 'sum',         # Partidos Titular
        'Suplente': 'sum',        # Partidos suplente
        'Completos': 'sum', # Partidos Completos
        'Minutos totales': 'sum', # Minutos
        'T': 'sum',               # Minutos titular
        'S': 'sum',               # Minutos suplentes
        'G': 'sum',               # Goles
        'A': 'sum',               # Amarillas
        'DA': 'sum',              # Dobles Amarillas
        'R': 'sum'                # Rojas
    }).reset_index()

    # Sacar jornada actual y numero de partidos jugados.

    #  Agrupamos por Jornada para ver cuántos minutos sumó EL EQUIPO en total en cada una
    # Esto crea una serie donde el índice es la Jornada y el valor la suma de minutos T
    minutos_por_jornada = df_long.groupby('Jornada')['T'].sum()

    # Filtramos: Nos quedamos solo con las jornadas donde se jugó (Suma T > 0)
    # Esto eliminará automáticamente las jornadas de descanso
    jornadas_activas = minutos_por_jornada[minutos_por_jornada > 0]

    if not jornadas_activas.empty:
        # La jornada actual es el número más alto registrado 
        jornada_actual = int(jornadas_activas.index.max())
        
        # Los partidos jugados son la CANTIDAD de jornadas activas
        partidos_jugados = len(jornadas_activas)
    else:
        jornada_actual = 0
        partidos_jugados = 0

    # Calculo de los minutos totales que hubiera jugado un jugador si lo hubiera jugado todo.
    min_totales_equipo = partidos_jugados * t_partido

    df_stats['Min_Posibles'] = df_stats['C_NC'] * t_partido 

    df_stats['G_x_min'] = df_stats['Minutos totales'] / df_stats['G']
    df_stats.loc[np.isinf(df_stats['G_x_min']), 'G_x_min'] = 0
    df_stats['G_x_min'] = df_stats['G_x_min'].round(1)
      
    df_stats['A_x_min'] = df_stats['Minutos totales'] / df_stats['A']
    df_stats.loc[np.isinf(df_stats['A_x_min']), 'A_x_min'] = 0
    df_stats['A_x_min'] = df_stats['A_x_min'].round(1)

    df_stats['R_x_min'] = df_stats['Minutos totales'] / df_stats['R']
    df_stats.loc[np.isinf(df_stats['R_x_min']), 'R_x_min'] = 0
    df_stats['R_x_min'] = df_stats['R_x_min'].round(1)

    df_stats["pct_participacion_disp"] = df_stats['Minutos totales'] / df_stats['Min_Posibles'] * 100 # Porcentaje de minutos jugados de los partidos que ha participado
    df_stats["pct_participacion_equipo"] = df_stats['Minutos totales'] / min_totales_equipo * 100 # Porcentaje de minutos jugados con respecto al total.
    
    # Renombramos columnas para que queden bonitas en la app
    df_stats.rename(columns={
        'C_NC': 'Convocatorias',
        'T': 'Minutos titular',
        'S': 'Minutos suplente',
        'G': 'Goles',
        'A': 'Amarillas',
        'DA': 'Dobles A.',
        'R': 'Rojas',
        'Min_Posibles': 'Min. Posibles',
        'pct_participacion_disp': '% Jugado (Disp)',
        'pct_participacion_equipo': '% Jugado (Total)'
    }, inplace=True)



    # Limpieza final: Eliminamos filas que no sean de jugadores (totales del excel, etc.)
    # Filtramos para que 'Nombre' no sea un número ni esté vacío
    df_stats = df_stats[~df_stats['Nombre'].astype(str).str.isnumeric()]
    df_stats = df_stats[df_stats['Nombre'] != 'nan']


    # --- RESULTADO ---
    st.dataframe(df_stats)
    return df_long, df_stats, jornada_actual, partidos_jugados, t_partido , None


# --- INTERFAZ ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/53/53283.png", width=100)
st.sidebar.title("Panel Técnico")


# 1. SELECTOR DE EQUIPO
equipo_seleccionado = st.sidebar.selectbox("Seleccionar Equipo", lista_equipos)

if st.sidebar.button("🔄 Actualizar Datos"):
    st.cache_data.clear()
    st.rerun()


# Cargar datos
df_full, df_stats, jornada_actual, partidos_jugados, t_partido, error = cargar_datos_equipo(equipo_seleccionado,lista_equipos[equipo_seleccionado])

if error:
    st.error(error)
else:
    # --- ENCABEZADO Y KPIs ---
    st.title(f"Informe: {equipo_seleccionado}")
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Goles a Favor", int(df_stats['Goles'].sum()))
    kpi2.metric("Tarjetas Amarillas", int(df_stats['Amarillas'].sum()))
    kpi3.metric("Plantilla", f"{len(df_stats)} jug.")
    kpi4.metric("Jornadas ", jornada_actual)
    

    st.markdown("---")

    # --- SECCIÓN 1: SEMÁFORO DE MINUTOS ---
    st.subheader("🚦 Estado de la Plantilla (Minutos Jugados)")
    
    # Clasificación
    df_stats['Rol_jugador'] = pd.cut(df_stats['% Jugado (Disp)'], 
                             bins=[-1, 30, 70, 1000], 
                             labels=['Rojo (<30%)', 'Naranja (30-70%)', 'Verde (>70%)'])
    
    df_stats['Rol_jugador_equipo'] = pd.cut(df_stats['% Jugado (Total)'], 
                             bins=[-1, 30, 70, 1000], 
                             labels=['Rojo (<30%)', 'Naranja (30-70%)', 'Verde (>70%)'])
    
    col_sem1, col_sem2 = st.columns([2, 1])
    
    with col_sem1:
        # Gráfico de barras coloreado por condición
        fig_sem = px.bar(df_stats, 
                         y='% Jugado (Disp)', 
                         x=df_stats["Nombre"], 
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
                         y='% Jugado (Total)', 
                         x=df_stats["Nombre"], 
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
        df_goles = df_stats[df_stats['Goles'] > 0].sort_values('Goles', ascending=True)
        if not df_goles.empty:
            fig_g = px.bar(df_goles, x='Goles', y=df_goles["Nombre"], orientation='h',
                           text='Goles', color='Goles', color_continuous_scale='Blues',
                           template="plotly_dark")
            st.plotly_chart(fig_g, use_container_width=True)
        else:
            st.info("Aún no hay goles registrados.")

    with c_tarj:
        st.subheader("🟨 Disciplina")
        df_ama = df_stats[df_stats['Amarillas'] > 0].sort_values('Amarillas', ascending=True)
        if not df_ama.empty:
            fig_a = px.bar(df_ama, x='Amarillas', y=df_ama["Nombre"], orientation='h',
                           text='Amarillas', color='Amarillas', color_continuous_scale='YlOrRd',
                           template="plotly_dark")
            st.plotly_chart(fig_a, use_container_width=True)
        else:
            st.info("Equipo limpio: 0 tarjetas.")

    # --- SECCIÓN 3: DETALLE JUGADOR ---
    st.markdown("---")
    jugador = st.selectbox("🔍 Analizar Jugador Específico", df_stats["Nombre"])
    
    if jugador:
        # Cogemos solo las filas de ese jugador en el histórico (df_long)
        datos_jugador = df_full[df_full['Nombre'] == jugador].copy()
        
        # ORDEN: Aseguramos que las jornadas salgan en orden (1, 2, 3...)
        datos_jugador = datos_jugador.sort_values('Jornada')

        fig_evo = go.Figure()
        fig_evo.add_trace(go.Bar(name='Titular', x=datos_jugador['Jornada'], y=datos_jugador['T'], marker_color='#2ecc71'))
        fig_evo.add_trace(go.Bar(name='Suplente',x=datos_jugador['Jornada'], y=datos_jugador['S'], marker_color='#f1c40f'))
        
        # Configuración del diseño
        fig_evo.update_layout(
            barmode='stack', title=f"Minutos por Jornada: {jugador}", 
            template="plotly_dark", yaxis_title="Minutos",
            xaxis_title="Jornada",
            # Esto hace que en el eje X ponga "J1, J2..." automáticamente
            xaxis=dict(tickmode='linear', tick0=1, dtick=1,tickprefix="J"))
        
        st.plotly_chart(fig_evo, use_container_width=True)

    # --- SECCIÓN 4: COMPARADOR HEAD-TO-HEAD ---
    st.markdown("---")
    st.subheader("⚔️ Comparador de Jugadores")
    
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        p1 = st.selectbox("Jugador A", df_stats["Nombre"], index=0)
    with col_sel2:
        # Intentamos que por defecto seleccione al segundo de la lista
        p2 = st.selectbox("Jugador B", df_stats["Nombre"], index=1 if len(df_stats) > 1 else 0)

    if p1 and p2:
        # Extraer datos
        stats_p1 = df_stats[df_stats['Nombre'] == p1].copy()
        stats_p2 = df_stats[df_stats['Nombre'] == p2].copy()
      
        # 1. TABLA COMPARATIVA CENTRAL
        # Usamos columnas para crear un efecto de "Marcador"
        c_p1, c_metric, c_p2 = st.columns([1, 1, 1])
        
        # Función auxiliar para mostrar métricas con colores
        def mostrar_comparacion(label, val1, val2, es_mejor_alto=True):
            # Aseguramos que si llega una Serie de Pandas, sacamos su valor escalar
            if isinstance(val1, pd.Series):
                val1 = val1.values[0]
            if isinstance(val2, pd.Series):
                val2 = val2.values[0]
                
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
        mostrar_comparacion("Minutos Totales", stats_p1['Minutos totales'], stats_p2['Minutos totales'])
        st.write("") # Espaciador
        mostrar_comparacion("Goles", stats_p1['Goles'], stats_p2['Goles'])
        st.write("")
        mostrar_comparacion("Amarillas", stats_p1['Amarillas'], stats_p2['Amarillas'], es_mejor_alto=False) # Menos es mejor

        # 2. GRÁFICO DE BARRAS COMPARATIVO
        st.write("")
        st.write("")
        
        fig_comp = go.Figure()
        metricas = ['Min. Titular', 'Min. Suplente', 'Goles (x100)', 'Amarillas (x100)']
        
        # Escalamos goles y amarillas x100 solo para que se vean en la gráfica junto a los minutos
        # (Esto es un truco visual, puedes quitarlo si prefieres normalizar de otra forma)
        vals_1 = [stats_p1['Minutos titular'].values[0], stats_p1['Minutos suplente'].values[0], stats_p1['Goles'].values[0]*100, stats_p1['Amarillas'].values[0]*100]
        vals_2 = [stats_p2['Minutos titular'].values[0], stats_p2['Minutos suplente'].values[0], stats_p2['Goles'].values[0]*100, stats_p2['Amarillas'].values[0]*100]

        fig_comp.add_trace(go.Bar(name=p1, x=metricas, y=vals_1, marker_color='#3498db'))
        fig_comp.add_trace(go.Bar(name=p2, x=metricas, y=vals_2, marker_color='#e74c3c'))

        fig_comp.update_layout(barmode='group', title="Comparativa Directa", template="plotly_dark")
        st.plotly_chart(fig_comp, use_container_width=True)
        st.caption("*Nota: Goles y Amarillas multiplicados x100 para visibilidad gráfica")


        # --- EXTRA 1: RADAR CHART (Sustituye el gráfico de barras del comparador por esto) ---
        st.write("---")
        st.subheader("🕸️ Comparativa Visual (Radar)")
        
        # 1. Normalización de datos (0-100) respecto al MÁXIMO DEL EQUIPO
        # Esto es vital para que el gráfico se vea bien
        def normalizar(valor, columna):
            max_val = df_stats[columna].max()
            if max_val == 0: return 0
            return (valor / max_val) * 100

        metricas_radar = ['Minutos totales', 'Goles', '% Jugado (Total)', 'Titular']
        nombres_radar = ['Minutos', 'Goles', '% Participación', 'Titularidades']
        
        vals_p1_norm = [normalizar(stats_p1[m].values[0], m) for m in metricas_radar]
        vals_p2_norm = [normalizar(stats_p2[m].values[0], m) for m in metricas_radar]
        
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


        # --- EXTRA 1: GRÁFICO DE EFICIENCIA (SCATTER PLOT) ---
        st.subheader("🎯 Eficiencia: Goles vs Minutos")
        
        # Filtramos para no ensuciar el gráfico con gente que no juega
        df_eficiencia = df_stats[df_stats['Minutos totales'] > 90].copy() 
        
        # Calculamos Goles por 90 min para el tamaño de la burbuja o el color
        df_eficiencia['Goles_90'] = (df_eficiencia['Goles'] / df_eficiencia['Minutos totales']) * 90
        
        fig_eff = px.scatter(df_eficiencia, 
                            x='Minutos totales', 
                            y='Goles',
                            size='Goles_90', # El tamaño de la bola es su promedio goleador
                            color='Goles',
                            hover_name=df_eficiencia["Nombre"],
                            text=df_eficiencia["Nombre"],
                            title="Relación Minutos jugados vs Goles marcados (Tamaño = Goles/90min)",
                            labels={'min_tot': 'Minutos Totales', 'goles': 'Goles Totales'},
                            template="plotly_dark")
        
        fig_eff.update_traces(textposition='top center')
        st.plotly_chart(fig_eff, use_container_width=True)



        
        # --- EXTRA 3: RACHA ÚLTIMOS 5 PARTIDOS ---
        st.subheader("🔥 Estado de Forma (Últimos 5 partidos)")
        
        # SELECCIONAR LOS ÚLTIMOS 5 PARTIDOS JUGADOS HASTA HOY
        # Filtramos jornadas anteriores o iguales a la actual y cogemos las últimas 5
        datos_jugador['Jornada'] = pd.to_numeric(datos_jugador['Jornada'], errors='coerce')
        last_5_df = datos_jugador[datos_jugador['Jornada'] <= jornada_actual].sort_values('Jornada').tail(5)

        # CÁLCULOS
        # Calculamos la suma de minutos (T + S) fila a fila
        last_5_df['Minutos_Partido'] = last_5_df['T'] + last_5_df['S']

        min_last_5 = last_5_df['Minutos_Partido'].sum()
        # Calculamos el máximo posible basándonos en cuántos partidos ha encontrado (pueden ser menos de 5 si estamos en la jornada 3)
        num_partidos_rango = len(last_5_df)
        max_possible_5 = num_partidos_rango * t_partido 

        if max_possible_5 > 0:
            pct_forma = (min_last_5 / max_possible_5) * 100
        else:
            pct_forma = 0

        # VISUALIZACIÓN
        c_forma1, c_forma2 = st.columns([1, 3])

        # Usamos int() para limpiar el visualizado
        c_forma1.metric("Minutos (Últ. 5)", int(min_last_5), f"{int(pct_forma)}% Disp.")

        # Mini gráfico de tendencia (Sparkline)
        # Usamos el DF last_5_df que ya tiene los datos listos
        fig_spark = px.line(last_5_df,x='Jornada', y='Minutos_Partido', markers=True, template="plotly_dark", title="Tendencia de minutos")

        fig_spark.update_layout(height=150, margin=dict(l=20, r=20, t=30, b=20), yaxis_range=[0, 100], # Un poco más de 90 para que no corte el punto
            xaxis=dict(tickmode='linear', dtick=1, tickprefix="J")) # Para que ponga J11, J12...
        c_forma2.plotly_chart(fig_spark, use_container_width=True)
        

        # ... tu código de carga y cálculos donde generas df_stats ...

        st.subheader("Verificación de Datos Calculados (df_stats)")

        # Opción Recomendada: Tabla interactiva (puedes ordenar y filtrar)
        st.dataframe(df_stats, use_container_width=True)

