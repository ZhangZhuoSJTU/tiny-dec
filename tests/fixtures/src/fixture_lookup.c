static int fetch(int index) {
    int values[4] = {2, 5, 8, 11};
    return values[index & 3];
}

static int run_lookup(int limit) {
    int total = 0;
    for (int i = 0; i < limit; i++) {
        int next = fetch(i);
        if (next < 10) {
            total = total + next;
        } else {
            total = total - i;
        }
    }
    return total;
}

int main(void) {
    return run_lookup(6);
}
