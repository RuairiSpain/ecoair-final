import pygame
#intitle:index.of mp3 -html -htm -php -asp -txt -pls


pygame.mixer.init()
pygame.mixer.music.load("/home/pi/ecoair/play/01 24K Magic.mp3")
pygame.mixer.music.play()
while pygame.mixer.music.get_busy() == True:
    continue