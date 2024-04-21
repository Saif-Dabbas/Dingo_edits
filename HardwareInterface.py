#!/usr/bin/env python3
import numpy as np
import math as m
import rospy
import RPi.GPIO as GPIO

class PWMParams:
    def __init__(self):
        for row in self.pins:
            for pin in row:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)

    def set_pwm(self, pin, duty_cycle):
        pwm_instance = GPIO.PWM(pin, self.freq)
        pwm_instance.start(duty_cycle)
        return pwm_instance

    def stop_pwm(self, pwm_instance):
        pwm_instance.stop()

class HardwareInterface:
    def __init__(self, link):
        self.pwm_max = 2400
        self.pwm_min = 370
        self.link = link
        self.servo_angles = np.zeros((3,4))
        self.pwm_params = PWMParams()  # New PWM parameters setup
        self.pins = np.array([[2, 14, 18, 23], [3, 15, 27, 24], [4, 17, 22, 25]])
        self.range = 4000
        self.freq = 250
        GPIO.setmode(GPIO.BCM)
        
        # Define the same configurations for servos
        self.pins = self.pwm_params.pins
        self.servo_multipliers = np.array([[-1, 1, 1, -1], [1, -1, 1, -1], [1, -1, 1, -1]])
        self.complementary_angle = np.array([[180, 0, 0, 180], [0, 180, 0, 180], [0, 180, 0, 180]])
        self.physical_calibration_offsets = np.array([[75, 130, 113, 73], [29, 13, 33, 15], [26, 12, 30, 4]])

        self.create()

    def create(self):
        # Set up PWM signals on all pins, adjusted for servos
        self.pwm_instances = {}
        for axis_index in range(3):
            for leg_index in range(4):
                pin = self.pins[axis_index][leg_index]
                duty_cycle = self.calculate_duty_cycle(0)  # Default to neutral position
                self.pwm_instances[pin] = self.pwm_params.set_pwm(pin, duty_cycle)

    def calculate_duty_cycle(self, angle):
        # Convert servo angle to duty cycle within PWM range
        return ((angle / 180) * (self.pwm_max - self.pwm_min) + self.pwm_min) / self.pwm_params.range * 100

    def set_actuator_positions(self, joint_angles):
        # Rest of your existing code for setting actuator positions, modifying to use PWMParams
        possible_joint_angles = impose_physical_limits(joint_angles)
        self.joint_angles_to_servo_angles(possible_joint_angles)
        
        for leg_index in range(4):
            for axis_index in range(3):
                pin = self.pins[axis_index][leg_index]
                angle = self.servo_angles[axis_index][leg_index]
                duty_cycle = self.calculate_duty_cycle(angle)
                self.pwm_instances[pin].ChangeDutyCycle(duty_cycle)

    def relax_all_motors(self, servo_list=np.ones((3, 4))):
        for axis_index in range(3):
            for leg_index in range(4):
                if servo_list[axis_index, leg_index] == 1:
                    pin = self.pins[axis_index][leg_index]
                    self.pwm_instances[pin].ChangeDutyCycle(0)

def joint_angles_to_servo_angles(self,joint_angles):
        """Converts joint found via inverse kinematics to the angles needed at the servo using linkage analysis.

        Parameters
        ----------
        joint_angles : 3x4 numpy array of float angles (radians)

        Returns
        -------
        servo_angles: 3x4 numpy array of float angles (degrees)
            The angles to be commanded of perfectly calibrated servos, rounded to 1dp
        
        """

        for leg in range(4):
            THETA2, THETA3 = joint_angles[1:,leg]

            THETA0 = lower_leg_angle_to_servo_angle(self.link, m.pi/2-THETA2, THETA3 + np.pi/2) # TODO draw a diagram to describe this transformatin from IK frame to LINK analysis frame

            #Adding offset from IK angle definition to servo angle definition, and conversion to degrees
            self.servo_angles[0,leg] = m.degrees( joint_angles[0,leg] ) # servo zero is same as IK zero
            self.servo_angles[1,leg] = m.degrees( THETA2              ) # servo zero is same as IK zero
            self.servo_angles[2,leg] = m.degrees( m.pi/2 + m.pi-THETA0) # servo zero is different to IK zero
        # print('Uncorrected servo_angles: ',self.servo_angles)

        # Adding final physical offset angles from servo calibration and clipping to 180 degree max
        self.servo_angles = np.clip(self.servo_angles + self.physical_calibration_offsets,0,180)
        
        # print('Unflipped servo_angles: ',self.servo_angles)

        #Accounting for difference in configuration of servos (some are mounted backwards)
        self.servo_angles  = np.round(np.multiply(self.servo_angles,self.servo_multipliers)+ self.complementary_angle,1)





### FUNCTIONS ###

def calculate_4_bar(th2 ,a,b,c,d):
    """Using 'Freudensteins method', it finds all the angles within a 4 bar linkage with vertices ABCD and known link lengths a,b,c,d
    defined clockwise from point A, and known angle, th2.

    Parameters
    ----------
    th2 : float
        the input angle at the actuating joint of the 4 bar linkage, aka angle DAB
    a,b,c,d: floats
        link lengths, defined in a clockwise manner from point A.
    
    Returns
    -------
    ABC,BCD,CDA: floats
        The remaining angles in the 4 bar linkage
    
    """
    # print('th2: ',m.degrees(th2),'a: ',a,'b: ',b,'c: ',c,'d: ',d)    
    x_b = a*np.cos(th2)
    y_b = a*np.sin(th2)
    
    #define diagnonal f
    f = np.sqrt((d-x_b)**2 +y_b**2)
    beta = np.arccos((f**2+c**2-b**2)/(2*f*c))
    gamma = np.arctan2(y_b,d-x_b)
    
    th4 = np.pi - gamma - beta
    
    x_c = c*np.cos(th4)+d
    y_c = c*np.sin(th4)
    
    th3 = np.arctan2((y_c-y_b),(x_c-x_b))
    
    
    ## Calculate remaining internal angles of linkage
    ABC = np.pi-th2 + th3
    BCD  = th4-th3
    CDA = np.pi*2 - th2 - ABC - BCD
                    
    return ABC,BCD,CDA
    


def lower_leg_angle_to_servo_angle(link, THETA2, THETA3):
    ''' Converts the direct angles of the upper and lower leg joint from the inverse kinematics to the angle
    at the servo that drives the lower leg via a linkage. 
    Parameters
        ----------
    THETA2 : float
        angle of upper leg from the IK 
    THETA3 : float
        angle of lower leg from the IK 
    link: Leg_linage
        A linkage class with all link lengths and relevant angles stored. Link values are based off
        the physcial design of the link

    Returns
    -------
    THETA0: float
        The angle of the servo that drives the outside of the linkage
    '''

    # First 4 bar linkages
    GDE,DEF,EFG = calculate_4_bar(THETA3 + link.lower_leg_bend_angle,link.i,link.h,link.f,link.g) #+ link.lower_leg_bend_angle
    # Triangle section
    CDH = 3/2*m.pi - THETA2 - GDE - link.EDC
    CDA = CDH +link.gamma #input angle
    # Second 4 bar linkage
    DAB,ABC,BCD = calculate_4_bar(CDA ,link.d,link.a,link.b,link.c)
    #Calculating Theta
    THETA0 = DAB + link.gamma

    return THETA0

def impose_physical_limits(desired_joint_angles):
    ''' Takes desired upper and lower leg angles and clips them to be within the range of physical possiblity. 
    This is because some angles are not possible for the physical linkage. Processing is done in degrees.
        ----------
    desired_joint_angles : numpy array 3x4 of float angles (radians)
        Desired angles of all joints for all legs from inverse kinematics

    Returns
    -------
    possble_joint_angles: numpy array 3x4 of float angles (radians)
        The angles that will be attempted to be implemeneted, limited to a possible range
    '''
    possible_joint_angles = np.zeros((3,4))

    for i in range(4):
        hip,upper,lower = np.degrees(desired_joint_angles[:,i])

        hip   = np.clip(hip,-20,20)
        upper = np.clip(upper,0,120)

        if      0    <=  upper <     10  :
            lower = np.clip(lower, -20 , 40) 
        elif 10    <=  upper <     20  :
            lower = np.clip(lower, -40 , 40)
        elif 20    <=  upper <     30  :
            lower = np.clip(lower, -50 , 40) 
        elif 30    <=  upper <     40  :
            lower = np.clip(lower, -60 , 30) 
        elif 40    <=  upper <     50  :
            lower = np.clip(lower, -70 , 25)
        elif 50    <=  upper <     60  :
            lower = np.clip(lower, -70 , 20) 
        elif 60    <=  upper <     70  :
            lower = np.clip(lower, -70 , 0) 
        elif 70    <=  upper <     80  :
            lower = np.clip(lower, -70 , -10)
        elif 80    <=  upper <     90  :
            lower = np.clip(lower, -70 , -20) 
        elif 90    <=  upper <     100  :
            lower = np.clip(lower, -70 , -30) 
        elif 100    <=  upper <     110  :
            lower = np.clip(lower, -70 , -40)
        elif 110    <=  upper <     120  :
            lower = np.clip(lower, -70 , -60) 

        possible_joint_angles[:,i] =  hip,upper,lower

    return np.radians(possible_joint_angles)

