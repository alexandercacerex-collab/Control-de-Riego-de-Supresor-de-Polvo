"""Control georreferenciado del riego de supresor de polvo sobre eje KMZ."""
from __future__ import annotations
import io
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import folium
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

ROOT = Path(__file__).parent
DB_PATH = ROOT / 'riego_registros.sqlite3'
COLS = ['id', 'fecha', 'inicio', 'fin', 'capa', 'empresa', 'unidad', 'producto', 'estado', 'volumen_m3', 'viajes', 'observacion', 'creado_en']
COLORS = {'Ejecutado': '#0b9d73', 'Programado': '#e8a100', 'En proceso': '#2878c8', 'Pendiente': '#e05a51'}
st.set_page_config(page_title='Control de riego | Eje vial', page_icon='💧', layout='wide')
st.markdown('''<style>.block-container{padding-top:1.2rem}.stMetric{background:#f2f7fa;padding:12px;border-radius:10px}</style>''', unsafe_allow_html=True)

@st.cache_resource
def load_eje():
    eje_path = ROOT / 'data' / 'eje.npz'
    if not eje_path.is_file():
        st.error('Falta el archivo data/eje.npz. Suba a GitHub la carpeta data con el archivo eje.npz en su interior, al mismo nivel que app.py.')
        st.stop()
    data = np.load(eje_path)
    return {k: data[k] for k in ('lon','lat','pk')}

@st.cache_resource
def database():
    con=sqlite3.connect(DB_PATH,check_same_thread=False)
    con.execute('''CREATE TABLE IF NOT EXISTS registros (id TEXT PRIMARY KEY, fecha TEXT, inicio REAL, fin REAL,
        capa TEXT, empresa TEXT, unidad TEXT, producto TEXT, estado TEXT, volumen_m3 REAL,
        viajes INTEGER, observacion TEXT, creado_en TEXT)''')
    con.commit()
    return con

def registros():
    return pd.read_sql_query('SELECT * FROM registros ORDER BY fecha DESC, creado_en DESC',database())

def guardar(row):
    con=database()
    con.execute('INSERT OR REPLACE INTO registros VALUES ('+','.join('?' for _ in COLS)+')', [row.get(c) for c in COLS]);con.commit()

def pk_text(v):
    x=int(round(float(v)))
    return f'{x//1000}+{x%1000:03d}'

def parse_pk(v):
    v=str(v).strip().replace(' ','').replace(',','.')
    if '+' in v:
        a,b=v.split('+',1)
        if not a.isdigit() or not b.isdigit() or len(b)>3 or int(b)>=1000:
            raise ValueError('Progresiva inválida: use 11+200 o 11200')
        return int(a)*1000+int(b)
    return float(v)

def slice_eje(eje, a, b, max_points=7000):
    pk=eje['pk'];lo=max(float(a),float(pk[0]));hi=min(float(b),float(pk[-1]))
    if lo>=hi:return []
    i=np.searchsorted(pk,lo,'left');j=np.searchsorted(pk,hi,'right')
    si=np.arange(max(0,i-1),min(len(pk),j+1))
    if len(si)>max_points:si=si[np.linspace(0,len(si)-1,max_points).astype(int)]
    # Estacas del eje están a intervalos de 5 m; insertar extremos interpolados.
    xs=np.r_[lo,pk[si],hi]
    xs=np.unique(np.clip(xs,lo,hi))
    return list(zip(np.interp(xs,pk,eje['lat']),np.interp(xs,pk,eje['lon'])))

def csv_bytes(df):
    return df.to_csv(index=False).encode('utf-8-sig')

def kmz_bytes(df,eje):
    from zipfile import ZipFile, ZIP_DEFLATED
    from xml.etree.ElementTree import Element,SubElement,tostring
    root=Element('kml',{'xmlns':'http://www.opengis.net/kml/2.2'}); doc=SubElement(root,'Document');SubElement(doc,'name').text='Riego supresor de polvo'
    for _,r in df.iterrows():
        pts=slice_eje(eje,r.inicio,r.fin,max_points=6000)
        if len(pts)<2:continue
        pm=SubElement(doc,'Placemark');SubElement(pm,'name').text=f"{r.capa}: {pk_text(r.inicio)} - {pk_text(r.fin)}"
        SubElement(pm,'description').text=f"{r.fecha} | {r.empresa} | {r.estado} | {r.volumen_m3} m3"
        style=SubElement(pm,'Style');ls=SubElement(style,'LineStyle')
        h=COLORS.get(r.estado,'#777777').lstrip('#');SubElement(ls,'color').text='ff'+h[4:6]+h[2:4]+h[0:2]
        SubElement(ls,'width').text='5'
        line=SubElement(pm,'LineString');SubElement(line,'tessellate').text='1'
        SubElement(line,'coordinates').text=' '.join(f'{lon:.8f},{lat:.8f},0' for lat,lon in pts)
    out=io.BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as z:z.writestr('doc.kml',tostring(root,encoding='utf-8',xml_declaration=True))
    return out.getvalue()

EJE=load_eje();MIN_PK=int(EJE['pk'][0]);MAX_PK=int(EJE['pk'][-1]);TOTAL=(MAX_PK-MIN_PK)/1000
st.title('💧 Control de riego y supresión de polvo')
st.caption(f'Eje georreferenciado LB-VEILLE-ESPINAR | {pk_text(MIN_PK)} a {pk_text(MAX_PK)} | {TOTAL:,.2f} km')
st.info('Los registros se guardan en SQLite en la instancia de Streamlit. En Streamlit Community Cloud el disco puede reiniciarse: descargue respaldos CSV periódicamente o configure almacenamiento externo para persistencia permanente.',icon='ℹ️')
tab_map,tab_reg,tab_dash,tab_data=st.tabs(['🗺️ Mapa y progresivas','➕ Registrar riego / crear capa','📊 Indicadores e informes','📁 Datos y exportación'])

with tab_reg:
    st.subheader('Crear capa de tramo / actividad')
    with st.form('nuevo_riego',clear_on_submit=False):
        c1,c2,c3=st.columns(3)
        with c1:
            fecha=st.date_input('Fecha de riego',value=date.today())
            ini=st.text_input('Progresiva inicial',value='11+200',help='Ejemplo: 12+450')
            fin=st.text_input('Progresiva final',value='12+200')
            capa=st.text_input('Nombre de la capa',value='Riego de control')
        with c2:
            empresa=st.text_input('Empresa / contratista')
            unidad=st.text_input('Cisterna / placa / unidad')
            producto=st.text_input('Supresor de polvo / dosificación',value='Agua')
            estado=st.selectbox('Estado',list(COLORS.keys()))
        with c3:
            volumen=st.number_input('Volumen aplicado (m³)',min_value=0.0,step=1.0)
            viajes=st.number_input('Número de viajes',min_value=0,step=1)
            obs=st.text_area('Observaciones')
        crear=st.form_submit_button('Guardar actividad y crear capa',type='primary')
    if crear:
        try:
            a,b=parse_pk(ini),parse_pk(fin)
            if not (MIN_PK<=a<b<=MAX_PK):raise ValueError(f'Rango válido: {pk_text(MIN_PK)} a {pk_text(MAX_PK)}, inicio menor que fin.')
            if not capa.strip():raise ValueError('Indique un nombre de capa.')
            guardar(dict(id=str(uuid4()),fecha=fecha.isoformat(),inicio=a,fin=b,capa=capa.strip(),empresa=empresa.strip(),unidad=unidad.strip(),producto=producto.strip(),estado=estado,volumen_m3=volumen,viajes=viajes,observacion=obs,creado_en=datetime.now().isoformat(timespec='seconds')))
            st.success(f'Capa guardada: {pk_text(a)} – {pk_text(b)} ({(b-a)/1000:.2f} km). Abra la pestaña del mapa.')
        except ValueError as e:st.error(str(e))

with tab_map:
    st.subheader('Localizador de progresivas y capas')
    cp1,cp2,cp3=st.columns([1,1,2])
    with cp1:q_ini=st.text_input('Buscar PK inicial','11+200',key='map_ini')
    with cp2:q_fin=st.text_input('Buscar PK final','12+200',key='map_fin')
    df=registros()
    with cp3:
        estados=st.multiselect('Visualizar estados',list(COLORS.keys()),default=list(COLORS.keys()))
    with st.expander('Filtrar capas existentes',expanded=False):
        companies=sorted([x for x in df.empresa.dropna().unique() if x]) if not df.empty else []
        companies_sel=st.multiselect('Empresa',companies,default=companies)
        if not df.empty:
            dmin=pd.to_datetime(df.fecha).min().date();dmax=max(date.today(),pd.to_datetime(df.fecha).max().date())
            fechas=st.date_input('Entre fechas',value=(dmin,dmax),key='map_dates')
        else:fechas=()
    try:
        a,b=parse_pk(q_ini),parse_pk(q_fin)
        if not MIN_PK<=a<b<=MAX_PK:raise ValueError('Progresivas fuera del eje o rango invertido.')
        center=[float(np.median(EJE['lat'])),float(np.median(EJE['lon']))]
        m=folium.Map(location=center,zoom_start=9,tiles='CartoDB positron',control_scale=True,prefer_canvas=True)
        base=folium.FeatureGroup(name='Eje principal',show=True)
        folium.PolyLine(slice_eje(EJE,MIN_PK,MAX_PK,4500),color='#536577',weight=3,opacity=.7,tooltip='Eje vial original').add_to(base)
        base.add_to(m)
        selected=folium.FeatureGroup(name='Tramo consultado',show=True)
        line=slice_eje(EJE,a,b)
        folium.PolyLine(line,color='#7c3aed',weight=7,opacity=.9,tooltip=f'Selección {pk_text(a)} – {pk_text(b)}').add_to(selected)
        for label,point,cl in [('Inicio',line[0],'green'),('Fin',line[-1],'red')]:
            folium.Marker(point,popup=f'{label}: {pk_text(a if label=="Inicio" else b)}',tooltip=label,icon=folium.Icon(color=cl)).add_to(selected)
        selected.add_to(m)
        view=df[df.estado.isin(estados)] if not df.empty else df
        if len(companies)>0:view=view[view.empresa.isin(companies_sel)]
        if len(fechas)==2:view=view[(view.fecha>=str(fechas[0]))&(view.fecha<=str(fechas[1]))]
        for state in estados:
            layer=folium.FeatureGroup(name=f'{state} ({sum(view.estado==state)})',show=True)
            for _,r in view[view.estado==state].iterrows():
                points=slice_eje(EJE,r.inicio,r.fin)
                if len(points)<2:continue
                label=f"{r.capa} | {pk_text(r.inicio)}–{pk_text(r.fin)} | {r.fecha} | {r.empresa} | {r.volumen_m3} m³"
                folium.PolyLine(points,color=COLORS[state],weight=6,opacity=.85,tooltip=label,popup=folium.Popup(label,max_width=420)).add_to(layer)
            layer.add_to(m)
        folium.LayerControl(collapsed=False).add_to(m)
        m.fit_bounds([line[0],line[-1]],padding=(25,25))
        st_folium(m,height=590,width=None,returned_objects=[],key='riego_map')
        c1,c2,c3=st.columns(3)
        c1.metric('Inicio',pk_text(a));c2.metric('Fin',pk_text(b));c3.metric('Tramo consultado',f'{(b-a)/1000:,.2f} km')
        st.caption('Línea morada: tramo buscado. Otros colores: estados de riego. Use el control de capas del mapa para mostrar u ocultar resultados.')
    except ValueError as e:st.error(str(e))

with tab_dash:
    st.subheader('Avance operativo e informes')
    df=registros()
    if df.empty:st.warning('Aún no existen actividades. Registre el primer tramo de riego.')
    else:
        f1,f2=st.columns(2)
        with f1:emp_sel=st.multiselect('Empresas',sorted(df.empresa.fillna('').unique()),default=sorted(df.empresa.fillna('').unique()),key='dash_empresa')
        with f2:statuses=st.multiselect('Estados',list(COLORS),default=list(COLORS),key='dash_estado')
        filtered=df[df.empresa.isin(emp_sel)&df.estado.isin(statuses)].copy()
        filtered['longitud_km']=(filtered.fin-filtered.inicio)/1000
        # Cálculo de cobertura mediante unión geométrica de intervalos; evita sumar doble por superposición.
        def coverage(sub):
            segs=sorted((float(r.inicio),float(r.fin)) for _,r in sub.iterrows())
            if not segs:return 0.0
            merged=[]
            for s,e in segs:
                if not merged or s>merged[-1][1]:merged.append([s,e])
                else:merged[-1][1]=max(e,merged[-1][1])
            return sum(e-s for s,e in merged)/1000
        executed=coverage(filtered[filtered.estado=='Ejecutado'])
        k1,k2,k3,k4,k5=st.columns(5)
        k1.metric('Actividades',len(filtered));k2.metric('Km únicos ejecutados',f'{executed:.2f}')
        k3.metric('Cobertura del eje',f'{executed/TOTAL*100:.1f}%')
        k4.metric('Volumen registrado',f'{filtered.volumen_m3.sum():,.1f} m³')
        k5.metric('Viajes registrados',int(filtered.viajes.sum()))
        st.caption('Los km únicos se calculan mediante la unión de intervalos ejecutados, evitando doble conteo de progresivas solapadas. Las aplicaciones repetidas sí se contabilizan como actividades y volumen.')
        d1,d2=st.columns(2)
        with d1:
            by_state=filtered.groupby('estado',as_index=False).agg(actividades=('id','count'),km_actividades=('longitud_km','sum'))
            st.plotly_chart(px.bar(by_state,x='estado',y='actividades',color='estado',color_discrete_map=COLORS,title='Actividades por estado'),use_container_width=True)
        with d2:
            by_day=filtered.groupby('fecha',as_index=False).agg(volumen_m3=('volumen_m3','sum'))
            st.plotly_chart(px.bar(by_day,x='fecha',y='volumen_m3',title='Volumen aplicado por fecha (m³)'),use_container_width=True)
        st.dataframe(filtered[['fecha','capa','inicio','fin','longitud_km','empresa','unidad','producto','estado','volumen_m3','viajes','observacion']],use_container_width=True,hide_index=True)
        st.download_button('Descargar informe filtrado (CSV)',csv_bytes(filtered),file_name='informe_riego_filtrado.csv',mime='text/csv')

with tab_data:
    st.subheader('Gestión, respaldo y exportación')
    df=registros()
    c1,c2=st.columns(2)
    with c1:
        st.download_button('Descargar todos los registros (CSV)',csv_bytes(df),file_name='respaldo_riego.csv',mime='text/csv',disabled=df.empty)
    with c2:
        st.download_button('Descargar capas georreferenciadas (KMZ)',kmz_bytes(df,EJE),file_name='capas_riego.kmz',mime='application/vnd.google-earth.kmz',disabled=df.empty)
    st.divider()
    st.markdown('**Importar registros desde un respaldo CSV**')
    upload=st.file_uploader('Seleccionar CSV exportado por esta aplicación',type=['csv'])
    if upload is not None:
        try:
            inc=pd.read_csv(upload,dtype={'id':str,'fecha':str,'capa':str,'empresa':str,'unidad':str,'producto':str,'estado':str,'observacion':str,'creado_en':str})
            if not set(COLS).issubset(inc.columns):raise ValueError('El archivo no contiene las columnas de respaldo requeridas.')
            st.write(f'Registros detectados: {len(inc)}')
            if st.button('Importar CSV (actualiza IDs existentes)'):
                count=0
                for _,r in inc.iterrows():
                    record={c:(None if pd.isna(r[c]) else r[c]) for c in COLS}
                    if not MIN_PK<=float(record['inicio'])<float(record['fin'])<=MAX_PK:continue
                    guardar(record);count+=1
                st.success(f'{count} registros importados.');st.rerun()
        except (ValueError,KeyError,UnicodeDecodeError) as e:st.error(str(e))
    st.divider()
    if not df.empty:
        st.markdown('**Eliminar un registro**')
        labels={f"{r.fecha} | {r.capa} | {pk_text(r.inicio)}–{pk_text(r.fin)} | {str(r.id)[:8]}":r.id for _,r in df.iterrows()}
        selected=st.selectbox('Registro a eliminar',list(labels))
        confirm=st.checkbox('Confirmo la eliminación permanente del registro seleccionado')
        if st.button('Eliminar registro',disabled=not confirm):
            database().execute('DELETE FROM registros WHERE id=?',(labels[selected],));database().commit();st.success('Registro eliminado');st.rerun()
    st.caption('Para trabajo multiusuario o conservación garantizada, sustituya SQLite local por PostgreSQL/Supabase. No publique archivos SQLite con registros operativos sensibles en GitHub.')
