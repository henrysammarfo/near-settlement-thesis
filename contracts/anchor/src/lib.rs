//! Settlemark anchor: logs the JSON arguments of `anchor` so the hashes it carries are
//! visible in the transaction's logs, and stores the latest one in contract state.
//! No SDK, no dependencies: only NEAR host functions.
#![no_std]

#[link(wasm_import_module = "env")]
extern "C" {
    fn input(register_id: u64);
    fn register_len(register_id: u64) -> u64;
    fn read_register(register_id: u64, ptr: u64);
    fn log_utf8(len: u64, ptr: u64);
    fn storage_write(key_len: u64, key_ptr: u64, value_len: u64, value_ptr: u64, register_id: u64) -> u64;
    fn panic_utf8(len: u64, ptr: u64) -> !;
}

#[panic_handler]
fn panic(_: &core::panic::PanicInfo) -> ! {
    core::arch::wasm32::unreachable()
}

static mut BUF: [u8; 4096] = [0; 4096];

#[no_mangle]
pub extern "C" fn anchor() {
    unsafe {
        input(0);
        let len = register_len(0);
        if len == u64::MAX || len as usize > 4096 - 18 {
            let m = b"input missing or over 4 KB";
            panic_utf8(m.len() as u64, m.as_ptr() as u64);
        }
        let prefix = b"settlemark anchor ";
        let buf = core::ptr::addr_of_mut!(BUF) as *mut u8;
        core::ptr::copy_nonoverlapping(prefix.as_ptr(), buf, prefix.len());
        read_register(0, buf.add(prefix.len()) as u64);
        let total = prefix.len() as u64 + len;
        log_utf8(total, buf as u64);
        let key = b"latest";
        storage_write(key.len() as u64, key.as_ptr() as u64, len, buf.add(prefix.len()) as u64, 1);
    }
}
