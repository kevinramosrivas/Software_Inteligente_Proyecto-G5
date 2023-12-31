
#importar librerias para scraping
#importamos las librerias necesarias
import pandas as pd
import streamlit as st
#guardar anime_features_df_matrix en un archivo para usarlo en el notebook de recomendacion
from scipy import sparse
import skops.io as sio
# importar librerias para hacer web scraping
import requests
from bs4 import BeautifulSoup
import re


# Poner un Titulo
st.title('Sistema de recomendación de animes de filtro colaborativo usando clustering')
# importamos el dataset que contiene los datos de los animes
anime = pd.read_csv('./data/Anime_Data_G5.csv')
#renombramos la columna de Id Anime a anime_id
anime.rename(columns={'Id Anime':'anime_id'}, inplace=True)
#leer los animes relevantes
anime_relevantes = pd.read_csv('./data/anime_relevantes.csv')

#importamos el dataset que contiene los datos de los usuarios
df = pd.read_csv('./data/User_Data_G5.csv')

#renombramos las columnas del dataset de usuarios
#cambiamos el nombre de la columna Id anime por anime_id
df.rename(columns={'Id Anime':'anime_id'}, inplace=True)
#cambiamos el nombre de la columna Id usuario por user_id
df.rename(columns={'Id usuario':'user_id'}, inplace=True)
#cambiamos el nombre de la columna Valoracion por rating
df.rename(columns={'Puntuacion':'rating'}, inplace=True)

#añadir el nombre de los animes al dataset de usuarios
df = pd.merge(df,anime[['anime_id','Titulo','Genero']],on='anime_id',how='left')

#eliminar los animes con menos de 10 valoraciones
df = df.groupby('anime_id').filter(lambda x : len(x)>10)


#cargamos el archivo anime_features_df_matrix.npz
anime_features_df_matrix = sparse.load_npz("./data/anime_features_df_matrix.npz")

# cargar el modelo
model_nearest = sio.load('./data/model_nearest.skops', trusted=True)

#tomar solo 80000 usuarios al azar
df = df.sample(n=80000, random_state=123)
#creamos la matriz de filtrado colaborativo
ratings_matrix = df.pivot_table(values='rating', index=['Titulo','anime_id','Genero'], columns=['user_id']).fillna(0)


class AnimeRecommender:
    MODEL_NAME = 'NearestNeighbors'
    # inicializamos el modelo, tiene como parametros el modelo de nearest neighbors, el dataframe de animes, los animes relevantes y el numero de vecinos
    def __init__(self, k_model, anime_features_df,relevant_anime, k):
        self.k_model = k_model
        self.anime_features_df = anime_features_df
        self.relevant_anime = relevant_anime
        self.k = k+1
        # dataframe de recomendaciones vacio
        self.recommendations = []
    # obtener el nombre del modelo
    def get_model_name(self):
        return self.MODEL_NAME
    
    #obtener las recomendaciones
    def get_anime_recommendation(self, anime_id):
        #obtener la posicion del anime en la matriz
        anime_localizado = ratings_matrix.loc[ratings_matrix.index.get_level_values('anime_id') == anime_id]
        if len(anime_localizado) == 0:
            st.write("No se encontro el anime")
            return
        #buscar un anime por su id
        query_index = ratings_matrix.index.get_loc(anime_localizado.index[0])
        distances, indices = self.k_model.kneighbors(ratings_matrix.iloc[query_index,:].values.reshape(1, -1), n_neighbors = self.k)
        #obtener los indices de los animes recomendados
        indices = indices.flatten()
        #obtener las distancias de los animes recomendados
        distances = distances.flatten()
        #crear un dataframe con los indices y las distancias
        df_indices = pd.DataFrame({'indices':indices,'distances':distances})
        #obtener los titulos de los animes recomendados
        df_indices['Titulo'] = df_indices['indices'].apply(lambda x: ratings_matrix.index[x][0])
        #obtener los generos de los animes recomendados
        df_indices['Genero'] = df_indices['indices'].apply(lambda x: ratings_matrix.index[x][2])
        #obtener las distancias de los animes recomendados
        df_indices['distances'] = df_indices['distances'].apply(lambda x: round(x,2))
        #obtener los indices de los animes recomendados
        df_indices['indices'] = df_indices['indices'].apply(lambda x: ratings_matrix.index[x][1])
        #obtener los titulos de los animes recomendados
        df_indices['Titulo'] = df_indices['Titulo'].apply(lambda x: x[:20])
        #creamos listas vacias para guardar los datos de los animes recomendados
        id_anime = []
        nombre_anime = []
        genero_anime = []

        #obetner los id, nombre y genero de los animes recomendados
        for i in range(0, len(distances.flatten())):
            id_anime.append(ratings_matrix.index[indices.flatten()[i]][1])
            nombre_anime.append(ratings_matrix.index[indices.flatten()[i]][0])
            genero_anime.append(ratings_matrix.index[indices.flatten()[i]][2])

        #crear un dataframe con los datos de los animes recomendados
        recomendaciones = pd.DataFrame({'anime_id':id_anime,'Titulo':nombre_anime,'Genero':genero_anime})
        #hacer un merge entre el dataframe de recomendaciones y el dataframe de animes
        recomendaciones = pd.merge(recomendaciones,anime[['anime_id','Titulo','Genero','Puntuacion general']],on='anime_id')
        #eliminar la primera fila del dataframe
        recomendaciones = recomendaciones.iloc[1:]
        #eliminar que existen columnas Titulo_x	 y Genero_x
        recomendaciones = recomendaciones.drop(['Titulo_x','Genero_x'],axis=1)
        # renombrar las columnas Titulo_y y Genero_y
        recomendaciones.rename(columns={'Titulo_y':'Titulo','Genero_y':'Genero'}, inplace=True)
        self.recommendations = recomendaciones
        return recomendaciones
    
    #obtener la precision de las recomendaciones para un k dado
    def calculate_precion(self, k):
        if k > len(self.relevant_anime):
            raise ValueError('k tiene que ser menor o igual que relevantes')
        if k > len(self.relevant_anime):
            raise ValueError('k tiene que ser menor o igual que recomendados')
        if k <= 0:
            raise ValueError('k tiene que ser mayor que 0')
        else:
            recomendados = self.recommendations
            #ordenar los recomendados por su rating
            recomendados = recomendados.sort_values(by='Puntuacion general',ascending=False)
            #tomar solo los k primeros recomendados
            recomendados = recomendados[:k]
            #hallar la cantidad de elementos de recomendados que estan en relevantes por su anime_id
            interseccion = self.relevant_anime[self.relevant_anime['anime_id'].isin(recomendados['anime_id'])]
            #hallar la precision
            precision = len(interseccion)/k
            # hacer un dataframe con la precision top@k
            precision_top_k = pd.DataFrame({'precision@'+str(k):[precision]})
            return precision_top_k
    
    # obtener el recall de las recomendaciones para un k dado
    def calculate_recall(self, k):
        if k > len(self.relevant_anime):
            raise ValueError('k tiene que ser menor o igual que relevantes')
        if k > len(self.recommendations):
            raise ValueError('k tiene que ser menor o igual que recomendados')
        if k <= 0:
            raise ValueError('k tiene que ser mayor que 0')
        else:
            recomendados = self.recommendations
            #ordenar los recomendados por su rating
            recomendados = recomendados.sort_values(by='Puntuacion general',ascending=False)
            #tomar solo los k primeros recomendados
            recomendados = recomendados[:k]
            #hallar la cantidad de elementos de recomendados que estan en relevantes por su anime_id
            interseccion = self.relevant_anime[self.relevant_anime['anime_id'].isin(recomendados['anime_id'])]
            #hallar la precision
            recall = len(interseccion)/len(self.relevant_anime)
            # hacer un dataframe con el recall top@k
            recall_top_k = pd.DataFrame({'recall@'+str(k):[recall]})
            return recall_top_k
        
    #obtener la precision de las recomendaciones para todos los k
    def calculate_precion_all(self):
        precision_all = pd.DataFrame()
        for k in range(3,self.k):
            precision = self.calculate_precion(k)
            precision_all = pd.concat([precision_all,precision],axis=1)
        return precision_all
    
    #obtener el recall de las recomendaciones para todos los k
    def calculate_recall_all(self):
        recall_all = pd.DataFrame()
        for k in range(3,self.k):
            recall = self.calculate_recall(k)
            recall_all = pd.concat([recall_all,recall],axis=1)
        return recall_all
    
# creamos una caja de texto para que el usuario ingrese el id del anime
anime_id = st.text_input("Ingrese el id del anime", "1")

#creamos un boton para que el usuario pueda obtener las recomendaciones
if st.button('Obtener recomendaciones'):
    # instanciamos la clase ContentRecommender
    anime_recommender = AnimeRecommender(model_nearest,anime_features_df_matrix,anime_relevantes,15)
    if anime_recommender == None:
        st.write("No se encontro el anime")
    else:
        #hacer scraping de la pagina de myanimelist
        url = 'https://myanimelist.net/anime/'+str(anime_id)
        # añadir el header
        headers = {'User-Agent': 'Mozilla/5.0'}
        #hacer el request a la pagina
        page = requests.get(url, headers=headers)
        #parsear el html
        soup = BeautifulSoup(page.content, 'html.parser')
        # obtener un div con clase leftside
        div = soup.find('div', class_='leftside')
        # obtener el div con clase text-align: center;
        div = div.find('div', style='text-align: center;')
        # buscar la etiqueta a
        a = div.find('a')
        #obtener todas las imagenes dentro de la etiqueta a
        img = a.find_all('img')
        #obtener la url de la imagen
        img = img[0]['data-src']
        # buscar el titulo del anime
        titulo = soup.find('div', class_='h1-title')
        # obtener el texto del titulo
        titulo = titulo.text
        # obtener el resumen del anime
        resumen = soup.find('p', itemprop='description')
        # obtener el texto del resumen
        resumen = resumen.text
        # hacer un bloque que divida en dos columnas
        col1, col2 = st.columns(2)
        # mostrar la imagen del anime
        col1.image(img, use_column_width=True)
        # mostrar el titulo del anime
        col2.header(titulo)
        # mostrar el resumen del anime
        col2.write(resumen)
        #obtenemos las recomendaciones
        recomendaciones = anime_recommender.get_anime_recommendation(int(anime_id))
        # ordenar las recomendaciones por su Puntaucion general
        recomendaciones = recomendaciones.sort_values(by='Puntuacion general',ascending=False)
        # poner un subtitulo
        st.subheader('Recomendaciones')
        #mostramos las recomendaciones
        st.write(recomendaciones)
        #obtenemos la precision de las recomendaciones
        precision = anime_recommender.calculate_precion_all()
        st.subheader('Precision y recall del modelo')
        #mostramos la precision de las recomendaciones
        st.write(precision)
        #obtenemos el recall de las recomendaciones
        recall = anime_recommender.calculate_recall_all()
        #mostramos el recall de las recomendaciones
        st.write(recall)





#hacer un footer
st.write('Hecho para el curso de Software Inteligente - G5')











