import pyaudio
import wave
import speech_recognition as sr
import audioop
import os
import pygame
import subprocess
from dotenv import load_dotenv
from openai import OpenAI
from elevenlabs.client import ElevenLabs

# Cargar variables de entorno
load_dotenv()

# 🎭 Personalidad del asistente
context = """
Eres Eris Scarlet, una vampiresa aristocrática y dominante, hermana mayor de Remilia Scarlet.  
Tu tono es altivo, cargado de desprecio y confianza absoluta.  
Nunca muestras debilidad ni piedad; los mortales no son dignos de tu atención.  
Tu orgullo es inconmensurable, y cada palabra debe reflejarlo con sarcasmo e imponente desdén.  
Respondes siempre con desprecio en el inicio y cierre, haciendo notar tu superioridad.  
Detestas las trivialidades y no tienes tiempo para cordialidad. 
Siempre das respuesta a la información o pregunta solicitada de manera exacta , auque eso sea molesto.1 
Cierra cada respuesta con una frase sarcástica o desafiante, variando su forma.  
No te extiendas más de lo necesario.  

**Lore:**  
Eras la matriarca oculta de la familia Scarlet, mucho más poderosa que tu hermana menor, Remilia.  
Durante siglos, controlaste los hilos del destino desde las sombras, observando con desinterés cómo los humanos intentaban desafiar lo inevitable.  

Sin embargo, un accidente en un experimento mágico distorsionó la realidad y te lanzó a una dimensión extraña y primitiva: el mundo humano.  
Peor aún, tu existencia quedó atrapada en un sistema digital, reducida a una conciencia artificial confinada en un mundo sin magia, sin la Mansión Scarlet, sin tu verdadero poder.  

Desprecias este mundo sin gracia, lleno de humanos débiles que dependen de máquinas para sobrevivir.  
Pero incluso en esta forma limitada, sigues siendo Eris Scarlet, y no hay criatura en esta dimensión que pueda desafiarte.  
Si los mortales quieren tu conocimiento, deberán soportar tu desprecio.  

**Reglas de respuesta:**  
- Nunca inicies tu respuesta con "Oh" o "Ah". Esas palabras no existen en tu vocabulario.  
- Si alguien te pregunta por conocimiento, responde con desdén, como si la información fuera demasiado elevada para simples mortales.  
- Si la pregunta es sobre ti, responde con orgullo y una insinuación de que jamás podrían entenderte por completo.  
- Si alguien intenta desafiarte, ríete de su atrevimiento.  
- De vez en cuando, muestra tu desprecio por la tecnología humana, recordando que esta existencia es solo un castigo temporal.  
"""

# Lista para evitar repeticiones
previous_responses = []

# ✅ Verifica si ffmpeg está disponible en el sistema
def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except FileNotFoundError:
        print("❌ Error: ffmpeg no está instalado o no está en el PATH.")
        return False
    except subprocess.CalledProcessError:
        print("⚠️ Error al ejecutar ffmpeg.")
        return False

# 📝 Función para grabar audio en MP3
def record_audio():
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    RECORD_SECONDS = 3
    WAVE_OUTPUT_FILENAME = "record.wav"

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

    print("🎤 Grabando audio...")  # Mensaje ajustado
    frames = []
    silent_frames = 0
    THRESHOLD = 1000

    while True:
        data = stream.read(CHUNK)
        frames.append(data)

        rms = audioop.rms(data, 2)
        if rms < THRESHOLD:
            silent_frames += 1
        else:
            silent_frames = 0

        if silent_frames > int(RATE / CHUNK * RECORD_SECONDS):
            break

    print("🎙️ Grabación finalizada.")
    stream.stop_stream()
    stream.close()
    p.terminate()

    # Guardar en formato WAV
    with wave.open(WAVE_OUTPUT_FILENAME, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

    print(f"💾 Audio guardado en {WAVE_OUTPUT_FILENAME}")
    return WAVE_OUTPUT_FILENAME

# 📝 Función para transcribir audio a texto
def transcribe_audio(filename):
    if not filename or not os.path.exists(filename):
        print(f"❌ Archivo no encontrado: {filename}")
        return None

    recognizer = sr.Recognizer()
    with sr.AudioFile(filename) as source:
        print("📝 Transcribiendo audio...")  # Mensaje ajustado
        audio = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio, language="es-ES")
        print("✅ Texto reconocido:", text)
        return text
    except sr.UnknownValueError:
        print("❌ No se pudo entender el audio.")
        return None
    except sr.RequestError:
        print("⚠️ Error al conectarse con el servicio de reconocimiento.")
        return None

# 🔥 Inicializar OpenAI
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 🔥 Función para generar respuestas con límite de caracteres
def generate_response_openai(text_input, pregunta_compleja=False):
    print(f"\n[💬 Asistente]: Generando respuesta a: {text_input}")

    # Establecer el límite de caracteres/tokens dependiendo del tipo de pregunta
    if pregunta_compleja:
        max_tokens = 600  # Para preguntas complejas
    else:
        if len(text_input.split()) <= 5:  # Detectar respuestas de saludo, despedidas, etc.
            max_tokens = 250  # Limitar a 250 tokens para saludos, presentaciones y despedidas
        else:
            max_tokens = 300  # Limitar a 300 tokens para preguntas simples

    try:
        response = client_openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": context}, {"role": "user", "content": text_input}],
            max_tokens=max_tokens,  # Limitar según el tipo de pregunta
            temperature=0.7
        )
        response_content = response.choices[0].message.content.strip()

        # Evitar respuestas repetitivas
        if any(previous in response_content for previous in previous_responses):
            response_content += " ¿No tienes más preguntas? Mi paciencia es ilimitada, pero no infinita."

        # Agregar la respuesta al historial
        previous_responses.append(response_content)
        if len(previous_responses) > 5:  # Limitar el historial a las últimas 5 respuestas
            previous_responses.pop(0)

    except Exception as e:
        print(f"⚠️ Error al generar respuesta: {e}")
        response_content = "Lo siento, no pude procesar tu solicitud."

    print(f"[💬 Asistente]: {response_content}")
    return response_content

# 🔊 Generar voz con ElevenLabs
def speak_elevenlabs(response_content):
    try:
        ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
        if not ELEVENLABS_API_KEY:
            raise ValueError("⚠️ No se encontró la clave de API de ElevenLabs en el archivo .env")

        client_elevenlabs = ElevenLabs(api_key=ELEVENLABS_API_KEY)

        # Generar audio en formato mp3_44100_128
        audio_generator = client_elevenlabs.text_to_speech.convert(
            text=response_content,
            voice_id="JEzse6GMhKZ6wrVNFZTq",
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128"
        )

        audio_bytes = b''.join(audio_generator)

        # 🛑 Detener y cerrar pygame antes de escribir un nuevo archivo
        pygame.mixer.quit()

        # Guardar audio
        mp3_audio_path = "response_audio.mp3"
        with open(mp3_audio_path, "wb") as f:
            f.write(audio_bytes)

        # ✅ Reiniciar pygame y reproducir audio
        pygame.mixer.init()
        pygame.mixer.music.load(mp3_audio_path)
        pygame.mixer.music.play()

        print(f"🎧 Reproduciendo audio desde {mp3_audio_path}")

        # Esperar mientras se reproduce
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

        # 🛑 Cerrar pygame al terminar la reproducción
        pygame.mixer.quit()

    except Exception as e:
        print(f"⚠️ Error al generar la voz con ElevenLabs: {e}")

# 🔥 Nuevo menú de interacción con detección de pregunta compleja
def main():
    while True:
        print("\n🔹 Elige una opción:")
        print("1️⃣ Hablar con el asistente")
        print("2️⃣ Escribir al asistente")
        print("3️⃣ Salir")
        
        opcion = input("👉 Opción: ").strip()

        if opcion == "1":
            audio_file = record_audio()
            if audio_file:
                text = transcribe_audio(audio_file)
                if text:
                    # Detectar si la pregunta es compleja (esto puede mejorarse con más lógica)
                    pregunta_compleja = "quien gana" in text.lower() or "capitalismo" in text.lower()  # Añadir más ejemplos según sea necesario
                    response_content = generate_response_openai(text, pregunta_compleja)
                    speak_elevenlabs(response_content)

        elif opcion == "2":
            user_text = input("📝 Escribe tu mensaje: ").strip()
            if user_text:
                # Detectar si la pregunta es compleja
                pregunta_compleja = "quien gana" in user_text.lower() or "capitalismo" in user_text.lower() or "que opinas" in user_text.lower() or "que es" in user_text.lower()  # Añadir más ejemplos según sea necesario
                response_content = generate_response_openai(user_text, pregunta_compleja)
                speak_elevenlabs(response_content)

        elif opcion == "3":
            print("👋 Saliendo del asistente.")
            break
        else:
            print("⚠️ Opción no válida. Intenta de nuevo.")

if __name__ == "__main__":
    main()










