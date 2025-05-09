from datetime import timedelta
from django.utils import timezone
from django.conf import settings

from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed




#Realizamos esta clase con el fin de definir un tiempo de expiracion para el token 
class ExpiringTokenAuthentication(TokenAuthentication):
    expired=False

    #CALCULA EL TIEMPO DE EXPIRACION
    def expires_in(self, token):
        #time_elapse es una variable que resta el tiempo actual y el tiempo en que fue creado el toque , para saber hace cuanto fue creado el token
        time_elapsed=timezone.now()-token.created
        #traemos el tiempo en fracciones de segundo de el archivo Settings.base.py para restarlo con el tiempo time_elapse
        left_time= timedelta(seconds= settings.TOKEN_EXPIRED_AFTER_SECONDS) - time_elapsed
        return left_time

    #ME DICE SI EL TOKEN A EXPIRADO 
    def is_token_expired(self,token):
        return self.expires_in(token)< timedelta(seconds=0)
    
    #creamos esta funcion para hacer referencia cuando se ha expirado un token
    #es una funcion que activa una actividad en cadenta con las is_token_expired despues con expired_in y posterior a esto nos muestra el valor
    def token_expire_handler(self,token):
       is_expired= self.is_token_expired(token)

       if is_expired:
           self.expired=True
           user=token.user
           token.delete()
           token=self.get_model().objects.create(user=user)  
           return is_expired,token
    
    def authenticate_credentials(self, key):
        message,token,user=None,None,None

        try:
            #Utilizamos get model por que el modelo de token tiene implementado una funcion llamada (get_model)
            token= self.get_model().objects.select_related('user').get(key=key)
            user=token.user

        except self.get_model().DoesNotExist:
            #AuthenticationFailed es una funcion definida en la documentacion de Token
            message= 'Token invalido.'
            self.expired=True 

        if token is not None:
            if not token.user.is_active:
                message='Usuario no activo o eliminado'
        
            is_expired =self.token_expire_handler(token)

            if is_expired:
                message='Su token a expirado'
           
        
        return(user,token,message,self.expired)
            
