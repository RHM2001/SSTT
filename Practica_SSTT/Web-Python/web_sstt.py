# coding=utf-8
#!/usr/bin/env python3

import socket
import selectors    #https://docs.python.org/3/library/selectors.html
import select
import types        # Para definir el tipo de datos data
import argparse     # Leer parametros de ejecución
import os           # Obtener ruta y extension
from datetime import datetime, timedelta # Fechas de los mensajes HTTP
import time         # Timeout conexión
import sys          # sys.exit
import re           # Analizador sintáctico
import logging      # Para imprimir logs



BUFSIZE = 8192 # Tamaño máximo del buffer que se puede utilizar
TIMEOUT_CONNECTION = 20 # Timout para la conexión persistente
MAX_ACCESOS = 10
TIMEOUT_COOKIE = 10
flag = True

# Extensiones admitidas (extension, name in HTTP)
filetypes = {"gif":"image/gif", "jpg":"image/jpg", "jpeg":"image/jpeg", "png":"image/png", "ico":"image/ico", "htm":"text/htm", 
"html":"text/html", "css":"text/css", "js":"text/js"}

# Configuración de logging
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s.%(msecs)03d] [%(levelname)-7s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger()


def enviar_mensaje(cs, data):
    """ Esta función envía datos (data) a través del socket cs
        Devuelve el número de bytes enviados.
    """
    cs.send(data)


def recibir_mensaje(cs):
    """ Esta función recibe datos a través del socket cs
        Leemos la información que nos llega. recv() devuelve un string con los datos.
    """
    return cs.recv(BUFSIZE)


def cerrar_conexion(cs):
    """ Esta función cierra una conexión activa.
    """
    cs.close()

# Elimino el parametro cs ya que no haría falta o eso creo.
# def process_cookies(headers,  cs):
def process_cookies(headers):
    """ Esta función procesa la cookie cookie_counter
        1. Se analizan las cabeceras en headers para buscar la cabecera Cookie - OK
        2. Una vez encontrada una cabecera Cookie se comprueba si el valor es cookie_counter - OK
        3. Si no se encuentra cookie_counter , se devuelve 1 - OK
        4. Si se encuentra y tiene el valor MAX_ACCESSOS se devuelve MAX_ACCESOS - OK
        5. Si se encuentra y tiene un valor 1 <= x < MAX_ACCESOS se incrementa en 1 y se devuelve el valor - OK
    """
    cookie = False
    val = -1

    for i in headers:
        if(i.find("Cookie") > -1):
            if(i.find("cookie_counter") > -1):
                cookie = True
                val = int(i.split(sep="=", maxsplit=-1)[1])
                break
    
    
    if(not cookie): 
        return 1
    elif(val < MAX_ACCESOS):
        return val+1
    else:  
        return MAX_ACCESOS   

def process_web_request(cs, webroot):
    """ Procesamiento principal de los mensajes recibidos.
        Típicamente se seguirá un procedimiento similar al siguiente (aunque el alumno puede modificarlo si lo desea)

        * Bucle para esperar hasta que lleguen datos en la red a través del socket cs con select() - OK 

            * Se comprueba si hay que cerrar la conexión por exceder TIMEOUT_CONNECTION segundos
            sin recibir ningún mensaje o hay datos. Se utiliza select.select - OK

            * Si no es por timeout y hay datos en el socket cs. - OK 
                * Leer los datos con recv. - OK
                * Analizar que la línea de solicitud y comprobar está bien formateada según HTTP 1.1
                    * Devuelve una lista con los atributos de las cabeceras. - OK
                    * Comprobar si la versión de HTTP es 1.1 - OK
                    * Comprobar si es un método GET. Si no devolver un error Error 405 "Method Not Allowed". - OK 
                    * Leer URL y eliminar parámetros si los hubiera - OK 
                    * Comprobar si el recurso solicitado es /, En ese caso el recurso es index.html - OK 
                    * Construir la ruta absoluta del recurso (webroot + recurso solicitado) - OK
                    * Comprobar que el recurso (fichero) existe, si no devolver Error 404 "Not found" - OK
                    * Analizar las cabeceras. Imprimir cada cabecera y su valor. Si la cabecera es Cookie comprobar
                    el valor de cookie_counter para ver si ha llegado a MAX_ACCESOS. - OK
                    Si se ha llegado a MAX_ACCESOS devolver un Error "403 Forbidden"
                    * Obtener el tamaño del recurso en bytes. - OK
                    * Extraer extensión para obtener el tipo de archivo. Necesario para la cabecera Content-Type - OK
                    * Preparar respuesta con código 200. Construir una respuesta que incluya: la línea de respuesta y
                    las cabeceras Date, Server, -> ¿¿Connection?? <-, Set-Cookie (para la cookie cookie_counter),
                    Content-Length y Content-Type. - ??
                    * Leer y enviar el contenido del fichero a retornar en el cuerpo de la respuesta.
                    * Se abre el fichero en modo lectura y modo binario - OK
                        * Se lee el fichero en bloques de BUFSIZE bytes (8KB) - OK 
                        * Cuando ya no hay más información para leer, se corta el bucle - OK

            * Si es por timeout, se cierra el socket tras el período de persistencia. - OK
                * NOTA: Si hay algún error, enviar una respuesta de error con una pequeña página HTML que informe del error. - OK
    """
    num_accesos_persistencia = 0

    while True:
        rsublist, wsublist, xsublist = select.select([cs], [], [], TIMEOUT_CONNECTION)

        if not rsublist:
            print("\n\nHa saltado el Timeout.", file=sys.stderr)
            cerrar_conexion(cs)
            sys.exit(-1)
        else:
            # Obtengo toda la cadena de la petición y le hago el decode para poder tratarla, además,
            # le hago un 'split' para separar todas las lineas y lo guardo todo en una lista.
            # La separación la hago con el separador '\r\n', no se si estaría bien
            data = recibir_mensaje(cs)

            if(not data):   
                cerrar_conexion(cs)
                sys.exit(-1)

            print("SOLICITUD")
            print(data.decode())


            # Donde voy a almacenar las cabeceras
            cabeceras = []
            
            data_str = data.decode()
            if '\r\n\r\n' in data_str:
                soli, cuer = data_str.split('\r\n\r\n', 1)
            else:
                soli = data_str
                cuer = ''

            soli = soli.split("\r\n")

            patron_get = r"(.*) (/.*) (HTTP/1.1)"
            er_get = re.compile(patron_get)
            res = er_get.fullmatch(soli[0])

            if (not res):
                ruta = webroot + "/errores/error400.html"
                ftype = os.path.basename(ruta).split(".")
                ftype = ftype[len(ftype)-1]
                respuesta = "HTTP/1.1 400 Bad Request" + "\r\nDate: " + str(datetime.today()) + "\r\nServer: sstt4896.org\r\nContent-Length: " + str(os.stat(ruta).st_size) + "\r\n" + "Content-Type: "+ filetypes[ftype] + "\r\nConnection: close\r\n\r\n"
                if(os.stat(ruta).st_size + len(respuesta) <= BUFSIZE):
                    with open(ruta, "rb") as f:
                        buffer = f.read()
                        to_send = respuesta.encode() + buffer
                        enviar_mensaje(cs, to_send)
                else:
                    enviar_mensaje(cs, respuesta.encode())
                    with open(ruta, "rb") as f:
                        while (1):
                            buffer = f.read(BUFSIZE)
                            if(not buffer):
                                break
                            enviar_mensaje(cs, buffer)

                cerrar_conexion(cs)
                sys.exit(-1)

            for i in range(len(soli)):
                if(i == 0):
                    solicitud = soli[0].split()
                else:
                    cabeceras.append(soli[i].strip())

            cuerpo = cuer.strip()
                
            recurso = solicitud[1].split(sep='?', maxsplit=1)[0]
            
            if solicitud[0] != "GET" and solicitud[0] != "POST":
                ruta = webroot + "/errores/error405.html"
                ftype = os.path.basename(ruta).split(".")
                ftype = ftype[len(ftype)-1]
                respuesta = "HTTP/1.1 405 Method Not Allowed" + "\r\nDate: " + str(datetime.today()) + "\r\nServer: sstt4896.org\r\nContent-Length: " + str(os.stat(ruta).st_size) + "\r\n" + "Content-Type: "+ filetypes[ftype] + "\r\nConnection: close\r\n\r\n"
                if(os.stat(ruta).st_size + len(respuesta) <= BUFSIZE):
                    with open(ruta, "rb") as f:
                        buffer = f.read()
                        to_send = respuesta.encode() + buffer
                        enviar_mensaje(cs, to_send)
                else:
                    enviar_mensaje(cs, respuesta.encode())
                    with open(ruta, "rb") as f:
                        while (1):
                            buffer = f.read(BUFSIZE)
                            if(not buffer):
                                break
                            enviar_mensaje(cs, buffer)

                cerrar_conexion(cs)
                sys.exit(-1)
            elif solicitud[0] == "POST":
                if(cuerpo.find("email=") > -1):
                    cuerpo_split = cuerpo.split(sep="%40")
                    if len(cuerpo_split) > 1 and cuerpo_split[1] == "um.es":
                        ruta = webroot + "/correoCorrecto.html"
                        file_type = os.path.basename(ruta).split(".")
                        file_type = file_type[len(file_type)-1]
                        respuesta = "HTTP/1.1 200 OK\r\nDate: " + str(datetime.today()) + "\r\nServer: sstt4896.org\r\nContent-Length: "
                        respuesta = respuesta + str(os.stat(ruta).st_size) + "\r\n" + "Content-Type: " + filetypes[file_type] + "\r\nKeep-Alive: timeout=" + str(TIMEOUT_CONNECTION+1) + ", max=" + str(MAX_ACCESOS) + "\r\nConnection: Keep-Alive\r\n\r\n"
                    else:
                        ruta = webroot + "/errores/error401.html"
                        ftype = os.path.basename(ruta).split(".")
                        ftype = ftype[len(ftype)-1]
                        respuesta = "HTTP/1.1 401  Unauthorized" + "\r\nDate: " + str(datetime.today()) + "\r\nServer: sstt4896.org\r\nContent-Length: " + str(os.stat(ruta).st_size) + "\r\n" + "Content-Type: "+ filetypes[ftype] + "\r\nConnection: close\r\n\r\n"
                        if(os.stat(ruta).st_size + len(respuesta) <= BUFSIZE):
                            with open(ruta, "rb") as f:
                                buffer = f.read()
                                to_send = respuesta.encode() + buffer
                                enviar_mensaje(cs, to_send)
                        else:
                            enviar_mensaje(cs, respuesta.encode())
                            with open(ruta, "rb") as f:
                                while (1):
                                    buffer = f.read(BUFSIZE)
                                    if(not buffer):
                                        break
                                    enviar_mensaje(cs, buffer)
                        cerrar_conexion(cs)
                        sys.exit(-1) 
            elif solicitud[0] == "GET":
                if num_accesos_persistencia < MAX_ACCESOS:
                    # Compruebo el recurso que se solicita
                    if recurso == "/":
                        num_accesos_cookie = process_cookies(cabeceras)
                        if(num_accesos_cookie >= TIMEOUT_COOKIE): 
                            ruta = webroot + "/errores/error403.html"
                            ftype = os.path.basename(ruta).split(".")
                            ftype = ftype[len(ftype)-1]
                            respuesta = "HTTP/1.1 403 Forbidden" + "\r\nDate: " + str(datetime.today()) + "\r\nServer: sstt4896.org\r\nContent-Length: " + str(os.stat(ruta).st_size) + "\r\n" + "Content-Type: "+ filetypes[ftype] + "\r\nConnection: close\r\n\r\n"
                            if(os.stat(ruta).st_size + len(respuesta) <= BUFSIZE):
                                with open(ruta, "rb") as f:
                                    buffer = f.read()
                                    to_send = respuesta.encode() + buffer
                                    enviar_mensaje(cs, to_send)
                            else:
                                enviar_mensaje(cs, respuesta.encode())
                                with open(ruta, "rb") as f:
                                    while (1):
                                        buffer = f.read(BUFSIZE)
                                        if(not buffer):
                                            break
                                        enviar_mensaje(cs, buffer)
                            cerrar_conexion(cs)
                            sys.exit(-1)
                        ruta = webroot + "/index.html"

                        if(not os.path.isfile(ruta)):
                            ruta = webroot + "/errores/error404.html"
                            ftype = os.path.basename(ruta).split(".")
                            ftype = ftype[len(ftype)-1]
                            respuesta = "HTTP/1.1 404 Not Found" + "\r\nDate: " + str(datetime.today()) + "\r\nServer: sstt4896.org\r\nContent-Length: " + str(os.stat(ruta).st_size) + "\r\n" + "Content-Type: "+ filetypes[ftype] + "\r\nConnection: close\r\n\r\n"
                            print(respuesta)
                            if(os.stat(ruta).st_size + len(respuesta) <= BUFSIZE):
                                with open(ruta, "rb") as f:
                                    buffer = f.read()
                                    to_send = respuesta.encode() + buffer
                                    enviar_mensaje(cs, to_send)
                            else:
                                enviar_mensaje(cs, respuesta.encode())
                                with open(ruta, "rb") as f:
                                    while (1):
                                        buffer = f.read(BUFSIZE)
                                        if(not buffer):
                                            break
                                        enviar_mensaje(cs, buffer)

                            cerrar_conexion(cs)
                            sys.exit(-1) 

                        file_type = os.path.basename(ruta).split(".")
                        file_type = file_type[len(file_type)-1]
                        respuesta = "HTTP/1.1 200 OK\r\nDate: " + str(datetime.today()) + "\r\nServer: sstt4896.org\r\nContent-Length: "
                        respuesta = respuesta + str(os.stat(ruta).st_size) + "\r\n"+ "Set-cookie: cookie_counter=" + str(num_accesos_cookie)+ "; Max-Age= "+ str(120) + "\r\n" + "Content-Type: " + filetypes[file_type] + "\r\nKeep-Alive: timeout=" + str(TIMEOUT_CONNECTION+1) + ", max=" + str(MAX_ACCESOS) + "\r\nConnection: Keep-Alive\r\n\r\n"
                    else:
                        ruta = webroot + recurso

                        if(not os.path.isfile(ruta)):
                            ruta = webroot + "/errores/error404.html"
                            ftype = os.path.basename(ruta).split(".")
                            ftype = ftype[len(ftype)-1]
                            respuesta = "HTTP/1.1 404 Not Found" + "\r\nDate: " + str(datetime.today()) + "\r\nServer: sstt4896.org\r\nContent-Length: " + str(os.stat(ruta).st_size) + "\r\n" + "Content-Type: "+ filetypes[ftype] + "\r\nConnection: close\r\n\r\n"
                            print(respuesta)
                            if(os.stat(ruta).st_size + len(respuesta) <= BUFSIZE):
                                with open(ruta, "rb") as f:
                                    buffer = f.read()
                                    to_send = respuesta.encode() + buffer
                                    enviar_mensaje(cs, to_send)
                            else:
                                enviar_mensaje(cs, respuesta.encode())
                                with open(ruta, "rb") as f:
                                    while (1):
                                        buffer = f.read(BUFSIZE)
                                        if(not buffer):
                                            break
                                        enviar_mensaje(cs, buffer)

                            cerrar_conexion(cs)
                            sys.exit(-1) 

                        file_type = os.path.basename(ruta).split(".")
                        file_type = file_type[len(file_type)-1]
                        num_accesos_cookie = process_cookies(cabeceras)
                        if(num_accesos_cookie == 1):
                            respuesta = "HTTP/1.1 200 OK\r\nDate: " + str(datetime.today()) + "\r\nServer: sstt4896.org\r\nContent-Length: "
                            respuesta = respuesta + str(os.stat(ruta).st_size) + "\r\n" + "Content-Type: " + filetypes[file_type] + "\r\nKeep-Alive: timeout=" + str(TIMEOUT_CONNECTION+1) + ", max=" + str(MAX_ACCESOS) + "\r\nConnection: Keep-Alive\r\n\r\n"
                        else:
                            respuesta = "HTTP/1.1 200 OK\r\nDate: " + str(datetime.today()) + "\r\nServer: sstt4896.org\r\nContent-Length: "
                            respuesta = respuesta + str(os.stat(ruta).st_size) + "\r\n"+ "Set-cookie: cookie_counter=" + str(num_accesos_cookie-1)+ "; Max-Age= "+ str(120) + "\r\n" + "Content-Type: " + filetypes[file_type] + "\r\nKeep-Alive: timeout=" + str(TIMEOUT_CONNECTION+1) + ", max=" + str(MAX_ACCESOS) + "\r\nConnection: Keep-Alive\r\n\r\n"
                    num_accesos_persistencia = num_accesos_persistencia + 1
                    if(num_accesos_persistencia >= 10 ):
                        flag = False
                    print(num_accesos_persistencia)
                elif(not flag):
                    ruta = webroot + "/errores/error403.html"
                    ftype = os.path.basename(ruta).split(".")
                    ftype = ftype[len(ftype)-1]
                    respuesta = "HTTP/1.1 403 Forbidden" + "\r\nDate: " + str(datetime.today()) + "\r\nServer: sstt4896.org\r\nContent-Length: " + str(os.stat(ruta).st_size) + "\r\n" + "Content-Type: "+ filetypes[ftype] + "\r\nConnection: close\r\n\r\n"
                    if(os.stat(ruta).st_size + len(respuesta) <= BUFSIZE):
                        with open(ruta, "rb") as f:
                            buffer = f.read()
                            to_send = respuesta.encode() + buffer
                            enviar_mensaje(cs, to_send)
                    else:
                        enviar_mensaje(cs, respuesta.encode())
                        with open(ruta, "rb") as f:
                            while (1):
                                buffer = f.read(BUFSIZE)
                                if(not buffer):
                                    break
                                enviar_mensaje(cs, buffer)
                    cerrar_conexion(cs)
                    sys.exit(-1) 
            
            # Printeo la solicitud
            print("RESPUESTA")
            print(respuesta)
            
            if(os.stat(ruta).st_size + len(respuesta) <= BUFSIZE):
                with open(ruta, "rb") as f:
                    buffer = f.read()
                    to_send = respuesta.encode() + buffer
                    enviar_mensaje(cs, to_send)
            else:
                enviar_mensaje(cs, respuesta.encode())
                with open(ruta, "rb") as f:
                    while (1):
                        buffer = f.read(BUFSIZE)
                        if(not buffer):
                            break
                        enviar_mensaje(cs, buffer)
                


def main():
    """ Función principal del servidor
    """

    try:

        # Argument parser para obtener la ip y puerto de los parámetros de ejecución del programa. IP por defecto 0.0.0.0
        parser = argparse.ArgumentParser()
        parser.add_argument("-p", "--port", help="Puerto del servidor", type=int, required=True)
        parser.add_argument("-ip", "--host", help="Dirección IP del servidor o localhost", required=True)
        parser.add_argument("-wb", "--webroot", help="Directorio base desde donde se sirven los ficheros (p.ej. /home/user/mi_web)")
        parser.add_argument('--verbose', '-v', action='store_true', help='Incluir mensajes de depuración en la salida')
        args = parser.parse_args()


        if args.verbose:
            logger.setLevel(logging.DEBUG)

        logger.info('Enabling server in address {} and port {}.'.format(args.host, args.port))

        logger.info("Serving files from {}".format(args.webroot))

        """ Funcionalidad a realizar
        * Crea un socket TCP (SOCK_STREAM) - OK
        * Permite reusar la misma dirección previamente vinculada a otro proceso. Debe ir antes de sock.bind - OK
        * Vinculamos el socket a una IP y puerto elegidos - OK

        * Escucha conexiones entrantes - OK

        * Bucle infinito para mantener el servidor activo indefinidamente - OK
            - Aceptamos la conexión - OK 

            - Creamos un proceso hijo - OK

            - Si es el proceso hijo se cierra el socket del padre y procesar la petición con process_web_request() - OK

            - Si es el proceso padre cerrar el socket que gestiona el hijo. - OK    
        """

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        sock.bind((args.host, args.port))

        # Cola de hasta MAX_ACCESOS conexiones 
        sock.listen()          

        while True:
            conn, addr  = sock.accept()

            pid = os.fork() 

            if pid == 0:
                cerrar_conexion(sock)
                process_web_request(conn, "/home/alumno/PracticasSSTT")
            else:
                cerrar_conexion(conn)

            

    except KeyboardInterrupt:
        True

if __name__== "__main__":
    main()
