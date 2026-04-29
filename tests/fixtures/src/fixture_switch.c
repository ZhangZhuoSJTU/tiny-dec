static int dispatch(int opcode, int value) {
    switch (opcode) {
        case 0:
            return value + 1;
        case 1:
            return value + 4;
        case 2:
            return value * 2;
        case 3:
            return value - 3;
        default:
            return -1;
    }
}

int main(void) {
    return dispatch(2, 9);
}
