from flask import Flask, render_template, request
import boto3
import json

app = Flask(__name__)

# Initialize Bedrock Runtime client
bedrock_runtime = boto3.client(
    service_name='bedrock-runtime',
    region_name='us-west-2'
)

# Initialize Amazon Location Service client
location_client = boto3.client(
    service_name='location',
    region_name='us-west-2'  # Cambia la región si es necesario
)

PLACE_INDEX_NAME = 'indice_medellin'  # Reemplaza con el nombre de tu Place Index

def get_coordinates(place_name):
    try:
        response = location_client.search_place_index_for_text(
            IndexName=PLACE_INDEX_NAME,
            Text=place_name,
            MaxResults=1
        )
        if response['Results']:
            coordinates = response['Results'][0]['Place']['Geometry']['Point']
            return coordinates
        else:
            return None
    except Exception as e:
        print(f"Error al obtener coordenadas para {place_name}: {str(e)}")
        return None

@app.route("/", methods=["GET", "POST"])
def index():
    response = None
    source_page = 'index'  # default
    if request.method == "POST":
        inicio = request.form.get("inicio")
        llegada = request.form.get("llegada")
        source_page = request.form.get("source_page") or 'index'

        print(f"Debug: Received inicio={inicio}, llegada={llegada}, source_page={source_page}")

        try:
            if source_page == 'page1':
                # Convertir nombres de lugares a coordenadas solo si viene de page1
                inicio_coords = get_coordinates(inicio)
                llegada_coords = get_coordinates(llegada)

                if not inicio_coords or not llegada_coords:
                    raise ValueError("No se pudieron encontrar las coordenadas para uno o ambos lugares proporcionados.")

                # Llamada a la calculadora de rutas de Amazon Location Service
                route_response = location_client.calculate_route(
                    CalculatorName='medellin_calculadora',  # Reemplaza con tu nombre de calculadora
                    DeparturePosition=inicio_coords,  # Coordenadas obtenidas del nombre del lugar
                    DestinationPosition=llegada_coords,  # Coordenadas obtenidas del nombre del lugar
                    TravelMode='Car'  # Puedes cambiar a 'Truck', 'Walking', etc.
                )

                # Procesar la respuesta
                distance = route_response['Summary']['Distance']
                duration = route_response['Summary']['DurationSeconds']
                legs = route_response.get('Legs', [])

                route_details = f"Distancia: {distance} km, Duración: {duration / 60:.2f} minutos."
                route_instructions = [f"Inicio: {leg['StartPosition']}, Fin: {leg['EndPosition']}" for leg in legs]

            elif source_page == 'page2':
                # No buscar coordenadas, prompt alternativo
                route_details = "Información de viaje no calculada, solo respuesta general."
                route_instructions = "No se calculó ruta específica."

            # Cambiar el prompt según la página de origen
            if source_page == 'page1':
                prompt = f"\n\nHuman: Quiero ir desde {inicio} hasta {llegada}. ¿Cuál es la mejor manera de llegar? No menciones precio\n\nAssistant:\n{route_details}\n\nInstrucciones de ruta: {route_instructions}"
            elif source_page == 'page2':
                prompt = f"\n\nHuman: ¿Qué opciones hay para conocer de {inicio} en {llegada}, Medellin?\n\nAssistant:\n{route_details}\n\nInstrucciones de ruta: {route_instructions}"
            else:  # Para 'index' u otras páginas por defecto
                prompt = f"\n\nHuman: Dame la mejor ruta para ir desde {inicio} hasta {llegada}\n\nAssistant:\n{route_details}\n\nInstrucciones de ruta: {route_instructions}"

            print(f"Debug: Generated prompt='{prompt}'")

            # Preparar el cuerpo de la solicitud para el modelo de Bedrock
            body = json.dumps({
                "prompt": prompt,
                "max_tokens_to_sample": 2000,
                "temperature": 0.7,
                "top_p": 1,
            })
            print(f"Debug: Request body='{body}'")

            # Llamada al modelo Bedrock (Claude)
            model_response = bedrock_runtime.invoke_model(
                modelId="anthropic.claude-v2",
                contentType="application/json",
                accept="application/json",
                body=body
            )

            # Asegurar que el cuerpo de la respuesta sea leído correctamente
            response_body = json.loads(model_response['body'].read().decode('utf-8'))
            print(f"Debug: Raw response body='{response_body}'")

            # Extraer la salida de la respuesta del modelo
            response = response_body.get('completion', "No response generated")
            print(f"Debug: Extracted response='{response}'")

        except Exception as e:
            # Capturar y mostrar cualquier excepción que ocurra
            print(f"Debug: Exception occurred='{str(e)}'")
            response = f"Error: {str(e)}"

    else:
        source_page = 'index'

    # Renderizar la plantilla adecuada basada en la página de origen
    if source_page == 'page1':
        return render_template("page1.html", response=response)
    elif source_page == 'page2':
        return render_template("page2.html", response=response)
    else:
        return render_template("index.html", response=response)

@app.route("/page1")
def page1():
    return render_template("page1.html")

@app.route("/page2")
def page2():
    return render_template("page2.html")

if __name__ == "__main__":
    app.run(debug=True)
