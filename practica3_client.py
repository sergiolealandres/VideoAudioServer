# import the library
from ast import Call
import threading
from appJar import gui
from PIL import Image, ImageTk
from call import *
import cv2
from conexion_servidor import *
from verification import *
import netifaces as ni


class VideoClient(object):

	selected_nick, selected_ip, selected_control_port, selected_data_port,selected_version=None,None, None,None,None
	camera_conected=0
	semaforo=threading.Lock()
	my_nick, my_ip, my_control_port, my_data_port, my_versions=None,None,None,None,None
	imagen_no_camera="imgs/nocamera.gif"
	accepted_call=0
	resolucion = "640x480"
	video_para_mostrar="imgs/video_por_defecto.gif"
	video_mostrado=0
	enviando=None
	stop_sending_video=False
	event_call=threading.Event()
	resolucion_sender="HIGH"
	resolucion_sender_value="640x480"
	resolucion_tuple = (640,480)
	sender_tuple = (640,480)
	searched_user=False
	cipher = False
	mute = False
	deafen = False
	cifrador=None
	chat=""

	def __init__(self, window_size):
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(("8.8.8.8", 80))
		self.local_IP = s.getsockname()[0]
		s.close()
		
		# Creamos una variable que contenga el GUI principal
		self.app = gui("Redes2 - P2P", window_size)
		self.app.setGuiPadding(10,10)

		self.app.setSize(1000,800)
		self.app.addLabel("title", "Cliente Multimedia P2P - Redes2 ")
		self.app.addImage("video", "imgs/nocamera.gif")
		self.app.setImageSize("video", 640, 480)
		# Registramos la función de captura de video
		# Esta misma función también sirve para enviar un vídeo
		self.cap = cv2.VideoCapture(self.imagen_no_camera)
		
		self.mode_webcam = False
		self.app.setPollTime(20)
		#self.app.registerEvent(self.capturaVideo)
		
		# Añadir los botones
		self.app.addButtons(["Desconectar Cam", "Salir"], self.buttonsCallback)
		self.app.setButton("Desconectar Cam", "Conectar Cam")
		self.app.setButtonFont(size=12, weight="bold", underline=False)

		self.app.startSubWindow("LLamada entrante", title="Recepción de llamada", modal=True)
		self.app.addLabel("Nick entrante", "")
		self.app.addImageButton("Aceptar",self.buttonsCallback,"icons/aceptar_llamada.png")
		self.app.addButtons([ "Rechazar"], self.buttonsCallback)
		self.app.stopSubWindow()
		

		self.app.startSubWindow("Panel de la llamada", modal=True)
		self.app.setStretch("both")
		self.app.setSticky("nesw")
		self.app.addImage("Video mostrado", self.imagen_no_camera)
		
		self.app.addScrolledTextArea("Chat",0,1)
		with self.app.tabbedFrame("Tabs llamada"):

			with self.app.tab("Opciones de llamada"):
				self.app.setFg("DarkBlue")
				self.app.setBg("LightSkyBlue")
				self.app.addButtons(["Colgar","Pausar", "Reanudar"],self.buttonsCallback)
				self.app.addLabelEntry("msj")
				self.app.addButton("Send", self.buttonsCallback)
			
			with self.app.tab("Opciones de Audio/Vídeo"):
				self.app.setFg("DarkBlue")
				self.app.setBg("LightSkyBlue")
				self.app.addButtons(["Webcam", "Video","Silenciar","Ensordecer"],self.buttonsCallback)
			
			with self.app.tab("Opciones de Resolución"):
				self.app.setFg("DarkBlue")
				self.app.setBg("LightSkyBlue")
				self.app.setInPadding([20,20])
				self.app.addButtons(["Resolución Baja","Resolución Media","Resolución Alta"],self.buttonsCallback)
		
		self.app.stopSubWindow()
		
		with self.app.tabbedFrame("Tabs"):
		# Tab para registrarse.
			
			with self.app.tab("Registrarse"):
				self.app.setFg("DarkBlue")
				self.app.setBg("LightSkyBlue")
				self.app.addLabelEntry("Nick\t\t", 0, 0)
				self.app.addLabelSecretEntry("Contraseña\t", 1, 0)
				self.app.addLabelEntry("IP\t\t", 2, 0)
				#self.app.addButton("IP VPN", self.buttonsCallback, 2,1)
				self.app.addLabelEntry("Puerto Control\t\t", 3, 0)
				self.app.addLabelEntry("Puerto Datos\t\t", 4, 0)
				self.app.addLabelEntry("Protocolo\t\t", 5, 0)
				self.app.addButtons(["Registrarse", "Clean"], self.buttonsCallback, 6, 0, 2)
				self.app.setEntryFocus("Nick\t\t")
				# Pone default values.
				self.app.setEntry("IP\t\t", self.local_IP)
				self.app.setEntry("Protocolo\t\t", "V0")
				self.app.setEntry("Puerto Control\t\t", "8080")
				self.app.setEntry("Puerto Datos\t\t", "4444")
			

			with self.app.tab("SEARCH USER"):
				self.app.setFg("DarkBlue")
				self.app.setBg("LightSkyBlue")
				self.app.addLabel("UserInfo", "", 0, 0)
				self.app.addLabelEntry("User\t\t", 1, 0)
				self.app.addButtons(["Search", "Call"], self.buttonsCallback, 6, 0, 2)
				

			with self.app.tab("LIST USERS"):
				self.app.setFg("DarkBlue")
				self.app.setBg("LightSkyBlue")

				users=list_users()
				nicks=[user[0] for user in users]
				self.app.addListBox("Usuarios Registrados", nicks, 0, 0, 1, 4)
				self.app.addButton("Actualizar", self.buttonsCallback, 0, 1)
				self.app.addButton("LLamar al usuario seleccionado", self.buttonsCallback, 1, 1)
                
                
		# Barra de estado
		# Debe actualizarse con información útil sobre la llamada (duración, FPS, etc...)

		self.app.setTabbedFrameDisabledTab("Tabs", "LIST USERS")
		self.app.setTabbedFrameDisabledTab("Tabs", "SEARCH USER")
		self.app.addStatusbar(fields=2)

	def start(self):
		self.app.go()

	# Función que captura el frame a mostrar en cada momento
	def capturaVideo(self):
		
		# Capturamos un frame de la cámara o del vídeo
		#print("hooola")
		ret, frame = self.cap.read()
		
		if frame is None and ret==False:
			
			return
		frame = cv2.resize(frame, (450,337))
		cv2_im = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
		img_tk = ImageTk.PhotoImage(Image.fromarray(cv2_im))		    

		# Lo mostramos en el GUI
		self.app.setImageData("video", img_tk, fmt = 'PhotoImage')

		# Aquí tendría que el código que envia el frame a la red
		# ...

	# Establece la resolución de la imagen capturada
	def setImageResolution(self, resolution):		
		# Se establece la resolución de captura de la webcam
		# Puede añadirse algún valor superior si la cámara lo permite
		# pero no modificar estos
		if resolution == "LOW":
			print("cambio a low")
			self.enviando.set(cv2.CAP_PROP_FRAME_WIDTH, 160) 
			self.enviando.set(cv2.CAP_PROP_FRAME_HEIGHT, 120) 
		elif resolution == "MEDIUM":
			self.enviando.set(cv2.CAP_PROP_FRAME_WIDTH, 320) 
			self.enviando.set(cv2.CAP_PROP_FRAME_HEIGHT, 240) 
		elif resolution == "HIGH":
			self.enviando.set(cv2.CAP_PROP_FRAME_WIDTH, 640) 
			self.enviando.set(cv2.CAP_PROP_FRAME_HEIGHT, 480) 


				
	# Función que gestiona los callbacks de los botones
	def buttonsCallback(self, button):

		if button =="Registrarse":

			if len(self.app.getEntry("Nick\t\t"))==0 or len(self.app.getEntry("Contraseña\t"))==0 \
				or len(self.app.getEntry("IP\t\t"))==0 or len(self.app.getEntry("Protocolo\t\t"))==0 \
				or len(self.app.getEntry("Puerto Control\t\t"))==0 \
				or len(self.app.getEntry("Puerto Datos\t\t"))==0:
				
				self.app.infoBox("Error","Some fields are not completed")
				return

			self.my_nick = self.app.getEntry("Nick\t\t")
			print(self.my_nick)
			if self.my_nick.count(" ")>0:
				self.app.infoBox("Error","Not valid Nick format")
				self.buttonsCallback("Clean")
				return

			password = self.app.getEntry("Contraseña\t")

			
			self.my_ip = self.app.getEntry("IP\t\t")
			
			self.my_versions = self.app.getEntry("Protocolo\t\t")
			self.my_control_port =(self.app.getEntry("Puerto Control\t\t"))
			self.my_data_port = (self.app.getEntry("Puerto Datos\t\t"))

			if validIP(self.my_ip)==False:
				self.app.infoBox("Error","Not valid IP")
				self.buttonsCallback("Clean")
				return

			if validPort(self.my_control_port)==False:
				self.app.infoBox("Error","Not valid control port")
				self.buttonsCallback("Clean")
				return

			if validPort(self.my_data_port)==False:
				self.app.infoBox("Error","Not valid data port")
				self.buttonsCallback("Clean")
				return

			if register(self.my_nick, self.my_ip, self.my_control_port, password, self.my_versions)==False:

				self.app.infoBox("Error","Wrong Password")
				return

			
			
			self.app.setTabbedFrameDisabledTab("Tabs", "LIST USERS", False)
			self.app.setTabbedFrameDisabledTab("Tabs", "SEARCH USER", False)
			thr = threading.Thread(target=call_waiter,args = (self.my_control_port, self, self.semaforo))
			thr.start()


		elif button =="Search":
			nick = self.app.getEntry("User\t\t")

			if len(nick)==0:

				self.app.infoBox("Error", "Debes de introducir algín nick")
				return

			data=query(nick)
			if data is None:

				self.app.infoBox("Error", nick + " no se ha encontrado")
				return
			
			self.selected_nick, self.selected_ip, self.selected_control_port, self.selected_version = data
			

			self.selected_control_port=(self.selected_control_port)
			self.app.setLabel("UserInfo", "Nick = " + nick + "\nIp = " +self.selected_ip + "\nPuerto de control = " + self.selected_control_port + "\nVersión = " + self.selected_version)
			self.searched_user=True

		elif button =="Call":

			if self.searched_user==False:
				self.app.infoBox("Error", "Busque primero un usuario para llamar")
				return
			
			if validIP(self.selected_ip)==False:
				self.app.infoBox("Error", self.selected_ip + " no es una ip válida")
				return

			if validPort(self.selected_control_port)==False:
				self.app.infoBox("Error","Not valid control port")
				return

			if "V1" in self.selected_version:
				self.cipher=True

			
			call(self.selected_nick, self.selected_ip, self.selected_control_port, self.my_ip, self.my_control_port, self.semaforo,self)

		
		elif button == "LLamar al usuario seleccionado":

			
			
			user_selected = self.app.getListBox("Usuarios Registrados")
			if user_selected == []:
				self.app.infoBox("Error", "Seleccione un usuario a llamar.")
				return

			nick = user_selected[0]

			data=query(nick)
			if data is None:
				self.app.infoBox("Error", nick + " no se ha encontrado")
				return

			self.selected_nick, self.selected_ip, self.selected_control_port, self.selected_version = data
			self.selected_control_port=(self.selected_control_port)
			if validIP(self.selected_ip)==False:
				self.app.infoBox("Error", self.selected_ip + " no es una ip válida")
				return

			if validPort(self.selected_control_port)==False:
				self.app.infoBox("Error","Not valid control port")
				return

			if dont_call_myself(self)==True:
				self.app.infoBox("Error","No puedes llamarte a ti mismo")
				return
			self.searched_user=True
			call(self.selected_nick, self.selected_ip, self.selected_control_port, self.my_ip, self.my_control_port, self.semaforo,self)
			

		elif button == 'Actualizar':


			users=list_users()
			nicks=[user[0] for user in users]
			self.app.updateListBox("Usuarios Registrados", nicks)


		elif button =="Clean":
			self.app.clearEntry("Nick\t\t")
			self.app.clearEntry("Contraseña\t")
			self.app.setEntry("IP\t\t", self.local_IP)
			self.app.setEntry("Protocolo\t\t", "V0")
			self.app.setEntry("Puerto Control\t\t", "8080")
			self.app.setEntry("Puerto Datos\t\t", "4444")
			self.app.setEntryFocus("Nick\t\t")

		elif button =="Pausar":
			if self.call_hold==False:
				self.call_hold=True
				parar_llamada(self)

		elif button =='Reanudar':
			if self.call_hold==True:
				
				continuar_llamada(self)
				self.call_hold=False
 
		elif button=='Salir':
			quit()
	    	
			self.app.stop() 

		elif button == 'Webcam':

			if self.video_mostrado==0:
				return

			self.video_mostrado=0
			self.enviando =cv2.VideoCapture(0)


		elif button == 'Video':
			self.app.setOnTop(stay=True)
			fichero= self.app.openBox(title=None, dirName="imgs", fileTypes=None, asFile=False, parent=None, multiple=False, mode='r')

			if fichero is None:
				return

			self.enviando = cv2.VideoCapture(fichero)

			self.video_mostrado=fichero


		elif button =="Aceptar":
			self.accepted_call=1
			self.event_call.set()

		elif button =="Rechazar":
			self.accepted_call=-1
			self.event_call.set()

		elif button == "Colgar":
			call_end(self)


		elif button == "Desconectar Cam":	

			if self.camera_conected==0:
				
				self.cap = cv2.VideoCapture(0)
				self.app.registerEvent(self.capturaVideo)
				self.camera_conected=1
				
				self.app.setButton("Desconectar Cam", "Desconectar Cam")
			else:

				self.camera_conected=0
				self.app.setButton("Desconectar Cam", "Conectar Cam")
				self.cap = cv2.VideoCapture(self.imagen_no_camera)
				#self.app.registerEvent(self.capturaVideo)

		elif button == "Resolución Baja":

			self.resolucion_sender="LOW"
			self.resolucion_sender_value="160x120"
			self.sender_tuple = (160,120)

		elif button == "Resolución Media":

			self.resolucion_sender="MEDIUM"
			self.resolucion_sender_value="320x240"
			self.sender_tuple = (320,240)

		elif button == "Resolución Alta":

			self.resolucion_sender="HIGH"
			self.resolucion_sender_value="640x480"
			self.sender_tuple = (640,480)
			
		
		elif button == "Silenciar":
			if(self.mute is False):
				self.mute = True
			else:
				self.mute = False
				self.audio_sender_event.set()
		elif button == "Ensordecer":
			if(self.deafen is False):
				self.deafen = True
			else:
				self.deafen = False
				self.receiver_sender_event.set()

		elif button == "Send":
			texto=self.app.getEntry("msj")
			texto_chat=self.my_nick+": "+texto+"\n\n"
			self.app.setTextArea("Chat", texto_chat, end=True, callFunction=False)
			#self.app.setMessage("Chat", self.chat)
			send_menssage(self,texto)



if __name__ == '__main__':

	vc = VideoClient("640x670")

	# Crear aquí los threads de lectura, de recepción y,
	# en general, todo el código de inicialización que sea necesario
	# ...


	# Lanza el bucle principal del GUI
	# El control ya NO vuelve de esta función, por lo que todas las
	# acciones deberán ser gestionadas desde callbacks y threads
	vc.start()

