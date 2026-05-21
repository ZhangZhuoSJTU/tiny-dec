static int tweak(int total, int outer, int inner) {
    int base = total + outer + inner;
    if ((outer & 1) == 0) {
        return base + 2;
    }
    return base - 3;
}

static int sweep(int rows, int cols) {
    int total = 0;
    for (int outer = 0; outer < rows; outer++) {
        for (int inner = 0; inner < cols; inner++) {
            int next = tweak(total, outer, inner);
            if (next < 25) {
                total = total + next;
            } else {
                total = total - inner;
            }
        }
    }
    return total;
}

int main(void) {
    return sweep(3, 4);
}
