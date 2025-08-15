#include <stdio.h>
#include <stdint.h>

#include "pico/stdlib.h"

#define N 1000000
#define EXPECTED_SUM 0xd495cdc0

void main()
{
    stdio_init_all();

    uint8_t iteration_counter = 0;

    for (;;)
    {
        volatile uint32_t sum = 0;

        // A glitch during this loop could corrupt the value of 'sum'.
        // Note that 'volatile' is used for both 'sum' and 'i' to increase
        // the variety of opcodes executed (memory access, etc.). This may
        // improve the likelihood of glitches having an observable effect.
        for (volatile uint32_t i = 0; i < N; i++)
        {
            sum += i * 2;
        }

        printf("Iteration %u - Sum = %lu\n", iteration_counter++, sum);

        // Check if the calculated sum matches the expected value.
        if (sum != EXPECTED_SUM)
        {
            printf("Glitch detected\n");
            // Infinite loop to halt execution if a glitch is detected.
            for (;;)
                ;
        }
    }
}
