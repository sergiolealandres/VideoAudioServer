# import the library
import threading
from appJar import gui
from PIL import Image, ImageTk
from cv2 import COLOR_BGR2RGB, cvtColor
from call import *
import call
import cv2
from conexion_servidor import *
from verification import *
from mss import mss

CAPTURA_VIDEO_SIZE = (450,337)
CKECK_SOCKET_TIMEOUT =3

class ScreenCapturer(object):
	sct = mss()
	def read(self):
		monitor = self.sct.monitors[1]
		sct_img = self.sct.grab(monitor)
		frame = np.array(Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX'))
		return True, cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
	def set(self,arg1,arg2):
		return
	def release(self):
		self.sct = None
		return

class VideoClient(object):

	selected_nick, selected_ip, selected_control_port, selected_data_port,selected_version=None,None, None,None,None
	camera_conected=0
	semaforo=threading.Lock()
	my_nick, my_ip, my_control_port, my_data_port, my_versions=None,None,None,None,None
	
	accepted_call=0
	resolucion = "640x480"
	
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
	chat=[]

	def __init__(self, window_size):
			
		self.imagen_no_camera = "imgs/nocamera.gif"
		self.video_para_mostrar =  "imgs/video_por_defecto.gif"
		self.video_mostrado = "imgs/video_por_defecto.gif"


		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(("8.8.8.8", 80))
		self.local_IP = s.getsockname()[0]
		s.close()
	
		# Creamos una variable que contenga el GUI principal
		self.app = gui("Redes2 - P2P", window_size)
		self.app.setGuiPadding(10,10)
		self.app.setSize(1000,800)
		self.app.setStopFunction(self.stop_function)
		# Preparación del interfaz
		self.app.addLabel("title", "Cliente Multimedia P2P - Redes2 ")
		self.app.addImage("video", "imgs/nocamera.gif")
		self.app.setImageSize("video", 640, 480)
		# Registramos la función de captura de video
		# Esta misma función también sirve para enviar un vídeo
		self.cap = cv2.VideoCapture(self.imagen_no_camera)
		self.mode_webcam = False
		self.app.setPollTime(20)
		
		# Añadir los botones
		self.app.addButtons(["Desconectar Cam", "Salir"], self.buttonsCallback)
		self.app.setButton("Desconectar Cam", "Conectar Cam")
		self.app.setButtonFont(size=12, weight="bold", underline=False)

		self.app.startSubWindow("LLamada entrante", title="Recepción de llamada", modal=True)
		self.app.addLabel("Nick entrante", "")
		self.app.addButtons(["Aceptar", "Rechazar"], self.buttonsCallback)
		self.app.stopSubWindow()
		
		self.app.startSubWindow("Panel de la llamada", modal=True)
		self.app.setStretch("both")
		self.app.setSticky("nesw")
		self.app.setStopFunction(self.stop_function)
		self.app.addImage("Video mostrado", self.imagen_no_camera)
		self.app.addListBox("Chat",self.chat,0,1)
		self.app.addEntry("msj",1,1)
		self.app.addButton("Send", self.buttonsCallback,2,1)
		with self.app.tabbedFrame("Tabs llamada"):

			with self.app.tab("Opciones de llamada"):
				self.app.setFg("DarkBlue")
				self.app.setBg("LightSkyBlue")
				self.app.addButtons(["Colgar","Pausar", "Reanudar"],self.buttonsCallback)
				
			with self.app.tab("Opciones de Audio/Vídeo"):
				self.app.setFg("DarkBlue")
				self.app.setBg("LightSkyBlue")
				self.app.addButtons(["Webcam", "Video","Capturar Pantalla","Silenciar","Ensordecer"],self.buttonsCallback)
			
			with self.app.tab("Opciones de Resolución"):
				self.app.setFg("DarkBlue")
				self.app.setBg("LightSkyBlue")
				self.app.setInPadding([20,20])
				self.app.addButtons(["Resolución Baja","Resolución Media","Resolución Alta"],self.buttonsCallback)

		self.app.addStatusbar(fields=2)
		self.app.setStatusbar("Time: 0", 0)
		self.app.setStatusbar("Fps: 0", 1)
		self.app.stopSubWindow()
		
		with self.app.tabbedFrame("Tabs"):
		# Tab para registrarse.
			
			with self.app.tab("Registrarse"):
				self.app.setFg("DarkBlue")
				self.app.setBg("LightSkyBlue")
				self.app.addLabelEntry("Nick\t\t", 0, 0)
				self.app.addLabelSecretEntry("Contraseña\t", 1, 0)
				self.app.addLabelEntry("IP\t\t", 2, 0)
				self.app.addLabelEntry("Puerto Control\t\t", 3, 0)
				self.app.addLabelEntry("Puerto Datos\t\t", 4, 0)
				self.app.addLabelEntry("Protocolo\t\t", 5, 0)
				self.app.addButtons(["Registrarse", "Clean"], self.buttonsCallback, 6, 0, 2)
				self.app.setEntryFocus("Nick\t\t")
				self.app.setEntry("IP\t\t", self.local_IP)
				self.app.setEntry("Protocolo\t\t", "V0#V1")
				self.app.setEntry("Puerto Control\t\t", "8080")
				self.app.setEntry("Puerto Datos\t\t", str(random.randint(MIN_PORT, MAX_PORT)))
			

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
		

	def start(self):
		self.app.go()

	# Función que captura el frame a mostrar en cada momento
	def capturaVideo(self):
		
		# Capturamos un frame de la cámara o del vídeo
		ret, frame = self.cap.read()
		
		if frame is None and ret==False:
			
			return
		frame = cv2.resize(frame, CAPTURA_VIDEO_SIZE)
		cv2_im = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
		img_tk = ImageTk.PhotoImage(Image.fromarray(cv2_im))		    

		# Lo mostramos en el GUI
		self.app.setImageData("video", img_tk, fmt = 'PhotoImage')

		# Aquí tendría que el código que envia el frame a la red
		# ...

	def stop_function(self):
		if call.current_call==1:
			
			call_end(self)
		return True

	# Establece la resolución de la imagen capturada
	def setImageResolution(self, resolution):		
		# Se establece la resolución de captura de la webcam
		# Puede añadirse algún valor superior si la cámara lo permite
		# pero no modificar estos
		if resolution == "LOW":
			self.enviando.set(cv2.CAP_PROP_FRAME_WIDTH, 160) 
			self.enviando.set(cv2.CAP_PROP_FRAME_HEIGHT, 120) 
		elif resolution == "MEDIUM":
			self.enviando.set(cv2.CAP_PROP_FRAME_WIDTH, 320) 
			self.enviando.set(cv2.CAP_PROP_FRAME_HEIGHT, 240) 
		elif resolution == "HIGH":
			self.enviando.set(cv2.CAP_PROP_FRAME_WIDTH, 640) 
			self.enviando.set(cv2.CAP_PROP_FRAME_HEIGHT, 480) 

	def disableTabs(self):
		self.app.setTabbedFrameDisabledTab("Tabs", "LIST USERS")
		self.app.setTabbedFrameDisabledTab("Tabs", "SEARCH USER")
				
	# Función que gestiona los callbacks de los botones
	def buttonsCallback(self, button):

		if button =="Registrarse":

			if len(self.app.getEntry("Nick\t\t"))==0 or len(self.app.getEntry("Contraseña\t"))==0 \
				or len(self.app.getEntry("IP\t\t"))==0 or len(self.app.getEntry("Protocolo\t\t"))==0 \
				or len(self.app.getEntry("Puerto Control\t\t"))==0 \
				or len(self.app.getEntry("Puerto Datos\t\t"))==0:
				self.disableTabs()
				self.app.infoBox("Error","Some fields are not completed")
				return

			self.my_nick = self.app.getEntry("Nick\t\t")

			if self.my_nick.count(" ")>0:
				self.app.infoBox("Error","Not valid Nick format")
				self.buttonsCallback("Clean")
				self.disableTabs()
				return

			password = self.app.getEntry("Contraseña\t")

			
			self.my_ip = self.app.getEntry("IP\t\t")
			
			self.my_versions = self.app.getEntry("Protocolo\t\t")
			self.my_control_port =(self.app.getEntry("Puerto Control\t\t"))
			self.my_data_port = (self.app.getEntry("Puerto Datos\t\t"))

			if validIP(self.my_ip)==False:
				self.app.infoBox("Error","Not valid IP")
				self.buttonsCallback("Clean")
				self.disableTabs()
				return

			if validPort(self.my_control_port)==False:
				self.app.infoBox("Error","Not valid control port")
				self.buttonsCallback("Clean")
				self.disableTabs()
				return

			if validPort(self.my_data_port)==False:
				self.app.infoBox("Error","Not valid data port")
				self.buttonsCallback("Clean")
				self.disableTabs()
				return

			if self.my_ip!=self.local_IP:

				res=self.app.questionBox("Warning", "The selected IP is not the local IP.\n\
					Are you sure you still want to register with this IP?", parent=None)

				if res==False:
					return
			
			checkSocket = socket.socket(socket. AF_INET, socket. SOCK_STREAM)
			location = (self.my_ip, int(self.my_data_port))
			checkSocket.settimeout(CKECK_SOCKET_TIMEOUT)
			try:
				resultCheck = checkSocket.connect_ex(location)

			except socket.timeout:

				self.app.infoBox("Error","Try again, not valid IP")
				checkSocket.close()
				return

			location = (self.my_ip, int(self.my_data_port)-1)


			try:
				resultCheck_audio = checkSocket.connect_ex(location)
			except socket.timeout:

				self.app.infoBox("Error","Try again, not valid IP")
				checkSocket.close()
				return
			checkSocket.close()
			if resultCheck == 0 or resultCheck_audio==0:
				self.app.infoBox("Error",
									"Selecciona otro puerto de datos, alguien está usando el "\
										+self.my_data_port+ " o bien el "+str(int(self.my_my_data_port)-1))
				self.disableTabs()
				return
			
			try:
				if register(self.my_nick, self.my_ip, self.my_control_port, password, self.my_versions)==False:

					self.app.infoBox("Error","Wrong Password")
					self.disableTabs()
					return
			except ServerErrorTimeout:
				self.app.infoBox("Error", "DS Timeout")
				self.disableTabs()
				return

			self.app.setTabbedFrameDisabledTab("Tabs", "LIST USERS", False)
			self.app.setTabbedFrameDisabledTab("Tabs", "SEARCH USER", False)
			self.app.setTabbedFrameDisabledTab("Tabs", "Registrarse")
			thr = threading.Thread(target=call_waiter,args = (self, self.semaforo))
			thr.start()


		elif button =="Search":
			nick = self.app.getEntry("User\t\t")

			if len(nick)==0:

				self.app.infoBox("Error", "Debes de introducir algún nick")
				return

			try:
				data=query(nick)
			except ServerErrorTimeout:
				self.app.infoBox("Error", "DS Timeout")
				return

			if data is None:

				self.app.infoBox("Error", nick + " no se ha encontrado")
				return
			
			self.selected_nick, self.selected_ip, self.selected_control_port, self.selected_version = data
			

			self.selected_control_port=(self.selected_control_port)
			self.app.setLabel("UserInfo", "Nick = " + nick + "\nIp = " +self.selected_ip + "\nPuerto de control = " \
				+ self.selected_control_port + "\nVersión = " + self.selected_version)
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

			if dont_call_myself(self)==True:
				self.app.infoBox("Error","No puedes llamarte a ti mismo")
				return

			if "V0" not in self.selected_version and "V1" not in self.selected_version:
				self.app.infoBox("Error","El usuario no soporta ni la V0 ni la V1")
				return

			if "V1" in self.selected_version:
				self.cipher=True

			
			call_user(self.semaforo,self)

		
		elif button == "LLamar al usuario seleccionado":

			user_selected = self.app.getListBox("Usuarios Registrados")
			if user_selected == []:
				self.app.infoBox("Error", "Seleccione un usuario a llamar.")
				return

			nick = user_selected[0]
			try:
				data=query(nick)

			except ServerErrorTimeout:
				self.app.infoBox("Error", "DS Timeout")
				return
			
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
			
			if "V0" not in self.selected_version and "V1" not in self.selected_version:
				self.app.infoBox("Error","El usuario no soporta ni la V0 ni la V1")
				return

			if "V1" in self.selected_version:
				self.cipher=True

			call_user(self.semaforo,self)
			

		elif button == 'Actualizar':


			users=list_users()
			nicks=[user[0] for user in users]
			self.app.updateListBox("Usuarios Registrados", nicks)


		elif button =="Clean":
			self.app.clearEntry("Nick\t\t")
			self.app.clearEntry("Contraseña\t")
			self.app.setEntry("IP\t\t", self.local_IP)
			self.app.setEntry("Protocolo\t\t", "V0#V1")
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
			try:
				quit()
			except ServerErrorTimeout:
				self.app.infoBox("Error", "DS Timeout")
				self.app.stop() 
	    	
			self.app.stop() 

		elif button == 'Webcam':

			if self.video_mostrado==0:
				return

			self.video_mostrado=0
			test =cv2.VideoCapture(0)
			if test is None or not test.isOpened():
				self.app.infoBox("Error","Ya está la cámara en uso",parent="Panel de la llamada")
				return

			self.enviando=test
				

		elif button == 'Capturar Pantalla':

			self.video_mostrado=-1
			self.enviando = ScreenCapturer()


		elif button == 'Video':
			#self.app.setOnTop(stay=True)
			fichero= self.app.openBox(title=None, dirName="imgs",fileTypes=[('video', '*.gif'),\
				 ('video', '*.mp4'),('video', '*.avi'), ('video', '*.mkv'),('video', '*.flv'),\
					  ('video', '*.mov'),('video', '*.divx'), ('video', '*.xvid'),('video', '*.rm'),\
						   ('video', '*.wmv'),('video', '*.mpg')], asFile=False, parent="Panel de la llamada", multiple=False, mode='r')

			if len(fichero)==0:
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
			self.app.hideSubWindow("Panel de la llamada", useStopFunction=False)
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
				self.audio_receiver_event.set()

		elif button == "Send":
			texto=self.app.getEntry("msj")
			texto_chat=self.my_nick+": "+texto
			self.chat.append(texto_chat)
			self.app.updateListBox("Chat", self.chat)
			send_menssage(self,texto)
			self.app.clearEntry("msj")


if __name__ == '__main__':

	vc = VideoClient("640x670")

	# Crear aquí los threads de lectura, de recepción y,
	# en general, todo el código de inicialización que sea necesario
	# ...


	# Lanza el bucle principal del GUI
	# El control ya NO vuelve de esta función, por lo que todas las
	# acciones deberán ser gestionadas desde callbacks y threads
	vc.start()


