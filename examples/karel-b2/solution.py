from tlfrobot import *

move()
move()
take()
turn_around()
move()
turn_right()
move()
turn_right()
while front_clear():
    move()
turn_right()
move()
print("done")
