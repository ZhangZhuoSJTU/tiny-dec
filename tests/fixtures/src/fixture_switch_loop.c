static int decode(int opcode, int value) {
    switch (opcode) {
        case 0:
            return value + 1;
        case 1:
            return value - 2;
        case 2:
            return value + 5;
        case 3:
            return value - 4;
        default:
            return value;
    }
}

static int execute(int limit) {
    int total = 0;
    for (int i = 0; i < limit; i++) {
        int code = i & 3;
        int next = decode(code, total + i);
        if (next < 12) {
            total = total + next;
        } else {
            total = total - code;
        }
    }
    return total;
}

int main(void) {
    return execute(6);
}
