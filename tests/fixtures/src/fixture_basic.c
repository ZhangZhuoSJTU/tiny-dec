#include <stdint.h>

static int helper(int x) {
    return x * 3 + 1;
}

int main(void) {
    int a = 7;
    int b = helper(a);
    return b - 2;
}
