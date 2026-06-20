#include "stm32f10x.h"

void logic_delay(uint32_t count) {
    while(count--);
}

int main(void) {
    RCC->APB2ENR |= (1 << 2) | (1 << 3); 

    GPIOB->CRL = 0x33333333; 
    GPIOB->CRH = (GPIOB->CRH & 0xFFFFF000) | 0x00000333; 
    GPIOB->CRH = (GPIOB->CRH & 0x0F00FFFF) | 0x33330000;
    GPIOA->CRL = 0x33333333;

    GPIOB->BSRR = (1 << 12) | (1 << 13);
    GPIOB->BRR  = (1 << 15); 

    logic_delay(500);

    for (uint16_t i = 0; i <= 256; i++) {
        GPIOB->BRR = 0x07FF; 
        GPIOB->BSRR = (i & 0x07FF);
        
        GPIOA->BRR = 0x00FF;
        GPIOA->BSRR = (i & 0x00FF);
        
        logic_delay(100); 

        GPIOB->BRR = (1 << 13); 
        logic_delay(200); 

        GPIOB->BSRR = (1 << 13);
        logic_delay(100); 
    }

    GPIOA->CRL = 0x44444444;

    GPIOB->BSRR = 0x07FF; 
    GPIOB->CRL = 0x44444444; 
    GPIOB->CRH = 0x33330444;

    GPIOB->BSRR = (1 << 12) | (1 << 13) | (1 << 15);

    while(1) {
    }
}